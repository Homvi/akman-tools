from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable

import pandas as pd

from src.length_calc import (
    STATUS_COMPLETE,
    STATUS_NONE,
    STATUS_PARTIAL,
    cable_pull_status,
    latest_pull_ends,
    parse_route,
)
from src.pathways import is_stuetze

DEFAULT_THIN_PACE = 20.0
DEFAULT_THICK_PACE = 3.0
DEFAULT_H_PER_STUETZE = 5.0
DEFAULT_HOURS_PER_WEEK = 56.0
DEFAULT_PULLERS = 1
DEFAULT_MAX_PER_ROOM = 5

_SPLIT_NODES = re.compile(r"[;,\n]+")
_EMPTY = {"", "<NA>", "nan", "None", "none"}


def _blank(value) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() in _EMPTY


def normalize_node(token: str) -> str:
    return str(token or "").strip()


def node_key(token: str) -> str:
    return normalize_node(token).casefold()


def parse_node_list(text) -> list[str]:
    raw = str(text or "").strip()
    if not raw or raw.lower() in _EMPTY:
        return []
    nodes: list[str] = []
    seen: set[str] = set()
    for part in _SPLIT_NODES.split(raw):
        token = normalize_node(part)
        if not token:
            continue
        key = node_key(token)
        if key in seen:
            continue
        seen.add(key)
        nodes.append(token)
    return nodes


def area_key(name: str, deck: str, area_ids: str) -> str:
    return "|".join(
        [
            str(name or "").strip(),
            str(deck or "").strip(),
            str(area_ids or "").strip(),
        ]
    )


@dataclass
class AreaDef:
    key: str
    name: str
    deck: str
    area_ids: str
    trays: list[str] = field(default_factory=list)
    penetrations: list[str] = field(default_factory=list)

    @property
    def nodes(self) -> list[str]:
        return list(dict.fromkeys([*self.trays, *self.penetrations]))

    @property
    def node_keys(self) -> set[str]:
        return {node_key(n) for n in self.nodes}

    @property
    def stuetzen(self) -> list[str]:
        return [n for n in self.nodes if is_stuetze(n)]


def parse_areas_excel(source) -> list[AreaDef]:
    """Parse Helység adatok sheet (header row with English column titles)."""
    df = pd.read_excel(source, sheet_name=0, header=0)
    cols = {str(c).strip().casefold(): c for c in df.columns}

    def col(*names: str):
        for name in names:
            hit = cols.get(name.casefold())
            if hit is not None:
                return hit
        return None

    c_name = col("Name of area", "name", "area", "helyiség")
    c_deck = col("Deck", "deck")
    c_ids = col("Number ID of that area.", "Number ID of that area", "area id", "id")
    c_trays = col("Cable trays in the area", "cable trays", "trays")
    c_pens = col("Penetrations", "penetrations")
    if c_name is None:
        raise ValueError("Areas Excel missing 'Name of area' column.")

    areas: list[AreaDef] = []
    for _, row in df.iterrows():
        name = "" if _blank(row.get(c_name)) else str(row.get(c_name)).strip()
        if not name:
            continue
        deck = "" if c_deck is None or _blank(row.get(c_deck)) else str(row.get(c_deck)).strip()
        ids = "" if c_ids is None or _blank(row.get(c_ids)) else str(row.get(c_ids)).strip()
        trays = parse_node_list(row.get(c_trays) if c_trays else "")
        pens = parse_node_list(row.get(c_pens) if c_pens else "")
        key = area_key(name, deck, ids)
        areas.append(
            AreaDef(
                key=key,
                name=name,
                deck=deck,
                area_ids=ids,
                trays=trays,
                penetrations=pens,
            )
        )
    return areas


def has_area_data(area: AreaDef) -> bool:
    """True if the room has at least one tray (kábelbán) or penetration listed."""
    return bool(area.trays or area.penetrations)


def areas_with_data(areas: list[AreaDef]) -> list[AreaDef]:
    return [a for a in areas if has_area_data(a)]


def _path_index(nodes: list[str], name: str) -> int | None:
    key = node_key(name)
    if not key:
        return None
    for i, node in enumerate(nodes):
        if node_key(node) == key:
            return i
    return None


def _path_indices_in_set(nodes: list[str], keys: set[str]) -> list[int]:
    return [i for i, node in enumerate(nodes) if node_key(node) in keys]


def _meters_between(distances: list[float], start_idx: int, end_idx: int) -> float:
    if start_idx > end_idx:
        start_idx, end_idx = end_idx, start_idx
    total = 0.0
    for i in range(start_idx, end_idx):
        if i < len(distances):
            total += float(distances[i] or 0.0)
    return total


def _endpoint(row: pd.Series, which: str) -> str:
    if which == "A":
        for col in ("Point_A", "Knoten_A"):
            val = row.get(col) if hasattr(row, "get") else None
            if val is not None and not _blank(val):
                return str(val).strip()
    else:
        for col in ("Point_E", "Knoten_E"):
            val = row.get(col) if hasattr(row, "get") else None
            if val is not None and not _blank(val):
                return str(val).strip()
    return ""


def _length_m(row: pd.Series) -> float:
    val = row.get("Length_m") if hasattr(row, "get") else None
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return 0.0
        return max(float(val), 0.0)
    except (TypeError, ValueError):
        return 0.0


def _thickness(row: pd.Series) -> str:
    val = row.get("Thickness") if hasattr(row, "get") else None
    text = str(val or "").strip()
    if text in {"Thick", "Thin", "Unknown"}:
        return text
    return "Unknown"


def _kabelnr(row: pd.Series) -> str:
    for col in ("Kabelnr", "Kabel", "join_key"):
        val = row.get(col) if hasattr(row, "get") else None
        if val is not None and not _blank(val):
            return str(val).strip()
    return ""


def _active_stop_location(row: pd.Series) -> str:
    """Latest Gestoppt Endsegment (else Startsegment), matching Stopped-page logic."""
    best_slot = None
    best_date = None
    for slot in (1, 2, 3):
        gcol = f"Gestoppt_{slot}"
        if gcol not in row.index and not hasattr(row, "get"):
            continue
        gval = row.get(gcol)
        if _blank(gval):
            continue
        try:
            ts = pd.Timestamp(gval)
        except (TypeError, ValueError):
            ts = pd.Timestamp.min
        if best_date is None or ts >= best_date:
            best_date = ts
            best_slot = slot
    if best_slot is None:
        return ""
    end = row.get(f"Endsegment_{best_slot}")
    if not _blank(end):
        return str(end).strip()
    start = row.get(f"Startsegment_{best_slot}")
    if not _blank(start):
        return str(start).strip()
    return ""


def classify_cable_in_area(row: pd.Series, area: AreaDef) -> dict | None:
    """Return touch info for one cable in one area, or None if no intersection."""
    pfad = row.get("Pfad") if hasattr(row, "get") else None
    nodes, distances = parse_route("" if _blank(pfad) else str(pfad))
    keys = area.node_keys
    if not keys or not nodes:
        return None
    hit_idx = _path_indices_in_set(nodes, keys)
    if not hit_idx:
        return None

    point_a = _endpoint(row, "A")
    point_e = _endpoint(row, "E")
    terminates = bool(
        (point_a and node_key(point_a) in keys) or (point_e and node_key(point_e) in keys)
    )
    stop_loc = _active_stop_location(row)
    stops = bool(stop_loc and node_key(stop_loc) in keys)
    through = not terminates

    status = cable_pull_status(row)
    thick = _thickness(row)
    length = _length_m(row)
    pulled = status == STATUS_COMPLETE

    remaining = 0.0
    if status == STATUS_COMPLETE:
        remaining = 0.0
    elif status == STATUS_NONE:
        remaining = length
    else:
        _, pull_end = latest_pull_ends(row)
        front_idx = _path_index(nodes, pull_end)
        first_area = min(hit_idx)
        last_area = max(hit_idx)
        target_idx = last_area
        if terminates:
            for ep in (point_a, point_e):
                if ep and node_key(ep) in keys:
                    ep_idx = _path_index(nodes, ep)
                    if ep_idx is not None:
                        target_idx = ep_idx
                        break
        if front_idx is None:
            # Started but front not on path — fall back to meters from area entry to target
            remaining = _meters_between(distances, first_area, target_idx)
        elif front_idx >= target_idx:
            remaining = 0.0
        else:
            remaining = _meters_between(distances, front_idx, target_idx)

    path_stuetzen = [
        nodes[i]
        for i in hit_idx
        if is_stuetze(nodes[i])
    ]
    # unique preserve order
    seen_s: set[str] = set()
    stuetzen_in_area: list[str] = []
    for s in path_stuetzen:
        k = node_key(s)
        if k in seen_s:
            continue
        seen_s.add(k)
        stuetzen_in_area.append(s)

    return {
        "kabelnr": _kabelnr(row),
        "thickness": thick,
        "status": status,
        "pulled": pulled,
        "through": through,
        "terminate": terminates,
        "stop": stops,
        "remaining_m": float(remaining),
        "length_m": length,
        "stuetzen": stuetzen_in_area,
        "path_nodes_in_area": [nodes[i] for i in hit_idx],
    }


def pull_front_passed_node(row: pd.Series, node: str) -> bool:
    """True if verlegt or pull front index >= node index on path."""
    if cable_pull_status(row) == STATUS_COMPLETE:
        return True
    pfad = row.get("Pfad")
    nodes, _ = parse_route("" if _blank(pfad) else str(pfad))
    idx = _path_index(nodes, node)
    if idx is None:
        return False
    status = cable_pull_status(row)
    if status == STATUS_NONE:
        return False
    _, pull_end = latest_pull_ends(row)
    front = _path_index(nodes, pull_end)
    if front is None:
        return False
    return front >= idx


def person_hours(
    thin_m: float,
    thick_m: float,
    *,
    thin_pace: float = DEFAULT_THIN_PACE,
    thick_pace: float = DEFAULT_THICK_PACE,
    unchecked_stuetzen: int = 0,
    h_per_stuetze: float = DEFAULT_H_PER_STUETZE,
) -> float:
    thin_pace = max(float(thin_pace or 0), 1e-9)
    thick_pace = max(float(thick_pace or 0), 1e-9)
    hours = max(float(thin_m), 0.0) / thin_pace + max(float(thick_m), 0.0) / thick_pace
    hours += max(int(unchecked_stuetzen), 0) * max(float(h_per_stuetze), 0.0)
    return hours


def add_workdays(start: date, workdays: int) -> date:
    """Advance `workdays` Mon–Fri days starting on `start` (counting start if weekday)."""
    n = int(workdays)
    if n <= 0:
        return start
    d = start
    remaining = n
    # Cap iterations
    for _ in range(n * 3 + 14):
        if d.weekday() < 5:
            remaining -= 1
            if remaining == 0:
                return d
        d += timedelta(days=1)
    return d


def next_workday_after(d: date) -> date:
    """First Mon–Fri strictly after `d`."""
    nxt = d + timedelta(days=1)
    for _ in range(8):
        if nxt.weekday() < 5:
            return nxt
        nxt += timedelta(days=1)
    return nxt


def kw_label(d: date) -> str:
    iso = d.isocalendar()
    return f"KW{int(iso.week):02d} {int(iso.year)}"


def estimate_schedule(
    person_hours_needed: float,
    *,
    pullers: float = DEFAULT_PULLERS,
    hours_per_week: float = DEFAULT_HOURS_PER_WEEK,
    as_of: date | None = None,
) -> dict:
    as_of = as_of or date.today()
    hours = max(float(person_hours_needed or 0.0), 0.0)
    pullers = max(float(pullers or 0.0), 0.0)
    hours_per_week = max(float(hours_per_week or 0.0), 0.0)
    if hours <= 0 or pullers <= 0 or hours_per_week <= 0:
        return {
            "person_hours": hours,
            "weekly_capacity": pullers * hours_per_week,
            "daily_capacity": (pullers * hours_per_week) / 5.0 if pullers and hours_per_week else 0.0,
            "workdays": 0,
            "end_date": as_of,
            "kw": kw_label(as_of),
        }
    weekly = pullers * hours_per_week
    daily = weekly / 5.0
    workdays = int(math.ceil(hours / daily - 1e-12))
    end = add_workdays(as_of, workdays)
    return {
        "person_hours": hours,
        "weekly_capacity": weekly,
        "daily_capacity": daily,
        "workdays": workdays,
        "end_date": end,
        "kw": kw_label(end),
    }


def _path_has_node(row: pd.Series, node: str) -> bool:
    pfad = row.get("Pfad") if hasattr(row, "get") else None
    nodes, _ = parse_route("" if _blank(pfad) else str(pfad))
    return _path_index(nodes, node) is not None


def stuetze_completion(
    area: AreaDef,
    cable_rows: list[tuple[pd.Series, dict]],
) -> list[dict]:
    """Per-area Stütze: cable completion % among cables that touch the area and hit the Stütze."""
    rows: list[dict] = []
    for st in area.stuetzen:
        relevant = [(row, info) for row, info in cable_rows if _path_has_node(row, st)]
        if not relevant:
            rows.append(
                {
                    "stuetze": st,
                    "cables": 0,
                    "done": 0,
                    "pct": 100.0,
                    "complete": True,
                }
            )
            continue
        done = sum(1 for row, _info in relevant if pull_front_passed_node(row, st))
        total = len(relevant)
        pct = 100.0 * done / total if total else 100.0
        rows.append(
            {
                "stuetze": st,
                "cables": total,
                "done": done,
                "pct": pct,
                "complete": done >= total,
            }
        )
    return rows


def summarize_area(
    area: AreaDef,
    df: pd.DataFrame,
    *,
    installed_stuetzen: Iterable[str] | None = None,
    thin_pace: float = DEFAULT_THIN_PACE,
    thick_pace: float = DEFAULT_THICK_PACE,
    h_per_stuetze: float = DEFAULT_H_PER_STUETZE,
    pullers: float = DEFAULT_PULLERS,
    hours_per_week: float = DEFAULT_HOURS_PER_WEEK,
    max_per_room: float = DEFAULT_MAX_PER_ROOM,
    as_of: date | None = None,
) -> dict:
    installed = {node_key(s) for s in (installed_stuetzen or [])}
    cable_infos: list[tuple[pd.Series, dict]] = []
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            info = classify_cable_in_area(row, area)
            if info is not None:
                cable_infos.append((row, info))

    thin_m = 0.0
    thick_m = 0.0
    zero_thin_m = 0.0
    zero_thick_m = 0.0
    n_total = len(cable_infos)
    n_pulled = 0
    n_thick = 0
    n_thin = 0
    n_through = 0
    n_terminate = 0
    n_stop = 0
    n_thick_through = 0
    n_thin_through = 0
    n_thick_term = 0
    n_thin_term = 0
    cable_ids: list[str] = []

    for _row, info in cable_infos:
        cable_ids.append(info["kabelnr"])
        length = float(info.get("length_m") or 0.0)
        if info["pulled"]:
            n_pulled += 1
        if info["thickness"] == "Thick":
            n_thick += 1
            thick_m += info["remaining_m"]
            zero_thick_m += length
        elif info["thickness"] == "Thin":
            n_thin += 1
            thin_m += info["remaining_m"]
            zero_thin_m += length
        else:
            # Unknown thickness: count toward thin meters conservatively
            thin_m += info["remaining_m"]
            zero_thin_m += length
        if info["through"]:
            n_through += 1
            if info["thickness"] == "Thick":
                n_thick_through += 1
            elif info["thickness"] == "Thin":
                n_thin_through += 1
        if info["terminate"]:
            n_terminate += 1
            if info["thickness"] == "Thick":
                n_thick_term += 1
            elif info["thickness"] == "Thin":
                n_thin_term += 1
        if info["stop"]:
            n_stop += 1

    stuetze_rows = stuetze_completion(area, cable_infos)
    unchecked = sum(1 for s in area.stuetzen if node_key(s) not in installed)
    hours = person_hours(
        thin_m,
        thick_m,
        thin_pace=thin_pace,
        thick_pace=thick_pace,
        unchecked_stuetzen=unchecked,
        h_per_stuetze=h_per_stuetze,
    )
    crew_cap = max(min(float(max_per_room or 0), float(pullers or 0)), 0.0)
    schedule = estimate_schedule(
        hours,
        pullers=crew_cap if crew_cap > 0 else pullers,
        hours_per_week=hours_per_week,
        as_of=as_of,
    )
    pulled_pct = (100.0 * n_pulled / n_total) if n_total else 100.0

    zero_hours = person_hours(
        zero_thin_m,
        zero_thick_m,
        thin_pace=thin_pace,
        thick_pace=thick_pace,
        unchecked_stuetzen=len(area.stuetzen),
        h_per_stuetze=h_per_stuetze,
    )
    room_weekly = crew_cap * float(hours_per_week or 0.0) if crew_cap > 0 else 0.0
    zero_weeks = (zero_hours / room_weekly) if room_weekly > 0 else 0.0

    return {
        "area": area,
        "cables": n_total,
        "cable_ids": cable_ids,
        "pulled": n_pulled,
        "pulled_pct": pulled_pct,
        "thick": n_thick,
        "thin": n_thin,
        "through": n_through,
        "terminate": n_terminate,
        "stop": n_stop,
        "thick_through": n_thick_through,
        "thin_through": n_thin_through,
        "thick_terminate": n_thick_term,
        "thin_terminate": n_thin_term,
        "remaining_thin_m": thin_m,
        "remaining_thick_m": thick_m,
        "remaining_m": thin_m + thick_m,
        "zero_thin_m": zero_thin_m,
        "zero_thick_m": zero_thick_m,
        "zero_person_hours": zero_hours,
        "zero_weeks": zero_weeks,
        "penetrations": len(area.penetrations),
        "stuetzen": stuetze_rows,
        "unchecked_stuetzen": unchecked,
        "person_hours": hours,
        "schedule": schedule,
        "cable_infos": cable_infos,
    }


def ordered_summaries(
    summaries: list[dict],
    priority_map: dict[str, int] | None = None,
) -> list[dict]:
    """
    Manual priority (lower int = sooner) first; unset keys fall back to
    highest Pulled %, then lowest remaining person-hours, then name.
    """
    priority_map = priority_map or {}

    def sort_key(s: dict):
        area = s["area"]
        manual = priority_map.get(area.key)
        has_manual = manual is not None
        return (
            0 if has_manual else 1,
            int(manual) if has_manual else 0,
            -float(s.get("pulled_pct") or 0.0),
            float(s.get("person_hours") or 0.0),
            str(area.name or "").casefold(),
            str(area.deck or "").casefold(),
        )

    return sorted(summaries, key=sort_key)


def _workdays_needed(person_hours_needed: float, crew: float, hours_per_week: float) -> int:
    hours = max(float(person_hours_needed or 0.0), 0.0)
    crew = max(float(crew or 0.0), 0.0)
    hours_per_week = max(float(hours_per_week or 0.0), 0.0)
    if hours <= 0 or crew <= 0 or hours_per_week <= 0:
        return 0
    daily = (crew * hours_per_week) / 5.0
    return int(math.ceil(hours / daily - 1e-12))


def schedule_areas(
    summaries: list[dict],
    *,
    pullers: float = DEFAULT_PULLERS,
    max_per_room: float = DEFAULT_MAX_PER_ROOM,
    hours_per_week: float = DEFAULT_HOURS_PER_WEEK,
    as_of: date | None = None,
    priority_map: dict[str, int] | None = None,
) -> list[dict]:
    """
    Parallel pool scheduler: each room gets up to max_per_room workers from the
    shared puller pool, in priority order. When a room finishes, freed workers
    go to the next waiting room.
    Mutates each summary's schedule and adds crew / queue_rank / start_date.
    """
    as_of = as_of or date.today()
    ordered = ordered_summaries(summaries, priority_map)
    pool = max(float(pullers or 0.0), 0.0)
    cap = max(float(max_per_room or 0.0), 0.0)
    hours_per_week = max(float(hours_per_week or 0.0), 0.0)

    # Annotate queue order
    for rank, s in enumerate(ordered, start=1):
        s["queue_rank"] = rank

    waiting = list(ordered)
    active: list[dict] = []  # {summary, crew, start, end, hours_left conceptually via end}
    free = pool
    now = as_of
    finished = 0
    safety = len(ordered) * 20 + 50

    while (waiting or active) and safety > 0:
        safety -= 1
        # Start as many waiting rooms as capacity allows
        started_any = False
        while waiting and free >= 1 and cap > 0:
            need = min(cap, free)
            if need < 1:
                break
            s = waiting.pop(0)
            hours = float(s.get("person_hours") or 0.0)
            crew = need
            if hours <= 0:
                sch = estimate_schedule(0, pullers=crew, hours_per_week=hours_per_week, as_of=now)
                s["crew"] = crew
                s["schedule"] = {
                    **sch,
                    "start_date": now,
                    "end_date": now,
                    "kw": kw_label(now),
                    "workdays": 0,
                    "weekly_capacity": crew * hours_per_week,
                    "daily_capacity": (crew * hours_per_week) / 5.0 if hours_per_week else 0.0,
                }
                finished += 1
                # crew freed immediately — don't hold workers for zero-hour rooms
                started_any = True
                continue
            workdays = _workdays_needed(hours, crew, hours_per_week)
            end = add_workdays(now, workdays)
            s["crew"] = crew
            s["schedule"] = {
                "person_hours": hours,
                "weekly_capacity": crew * hours_per_week,
                "daily_capacity": (crew * hours_per_week) / 5.0,
                "workdays": workdays,
                "start_date": now,
                "end_date": end,
                "kw": kw_label(end),
            }
            active.append({"summary": s, "crew": crew, "end": end})
            free -= crew
            started_any = True

        if not active:
            if not waiting:
                break
            if not started_any:
                # Cannot start any room (e.g. pool < 1) — mark remaining with zero crew
                for s in waiting:
                    hours = float(s.get("person_hours") or 0.0)
                    s["crew"] = 0
                    s["schedule"] = estimate_schedule(
                        hours, pullers=0, hours_per_week=hours_per_week, as_of=now
                    )
                    s["schedule"]["start_date"] = now
                waiting.clear()
                break
            continue

        # Advance past next completion so freed crew can start the next room
        # on the following workday (no same-day double-booking of the last day).
        next_end = min(job["end"] for job in active)
        still_active = []
        for job in active:
            if job["end"] <= next_end:
                free += job["crew"]
                finished += 1
            else:
                still_active.append(job)
        active = still_active
        now = next_workday_after(next_end)

    # Ensure every summary has crew/schedule fields
    for s in summaries:
        s.setdefault("crew", float(s.get("crew") or 0))
        sch = s.get("schedule") or {}
        if "start_date" not in sch:
            sch["start_date"] = as_of
            s["schedule"] = sch
        s.setdefault("queue_rank", 0)

    return ordered


def summarize_all_areas(
    areas: list[AreaDef],
    df: pd.DataFrame,
    *,
    installed_by_area: dict[str, Iterable[str]] | None = None,
    thin_pace: float = DEFAULT_THIN_PACE,
    thick_pace: float = DEFAULT_THICK_PACE,
    h_per_stuetze: float = DEFAULT_H_PER_STUETZE,
    pullers: float = DEFAULT_PULLERS,
    hours_per_week: float = DEFAULT_HOURS_PER_WEEK,
    max_per_room: float = DEFAULT_MAX_PER_ROOM,
    as_of: date | None = None,
    priority_map: dict[str, int] | None = None,
    only_with_data: bool = True,
) -> list[dict]:
    installed_by_area = installed_by_area or {}
    visible = areas_with_data(areas) if only_with_data else list(areas)
    summaries = [
        summarize_area(
            area,
            df,
            installed_stuetzen=installed_by_area.get(area.key, ()),
            thin_pace=thin_pace,
            thick_pace=thick_pace,
            h_per_stuetze=h_per_stuetze,
            pullers=pullers,
            hours_per_week=hours_per_week,
            max_per_room=max_per_room,
            as_of=as_of,
        )
        for area in visible
    ]
    schedule_areas(
        summaries,
        pullers=pullers,
        max_per_room=max_per_room,
        hours_per_week=hours_per_week,
        as_of=as_of,
        priority_map=priority_map,
    )
    return ordered_summaries(summaries, priority_map)


def cables_hitting_nodes(df: pd.DataFrame, nodes: Iterable[str]) -> set[str]:
    keys = {node_key(n) for n in nodes if normalize_node(n)}
    if not keys or df is None or df.empty or "Pfad" not in df.columns:
        return set()
    hit: set[str] = set()
    for _, row in df.iterrows():
        path_nodes, _ = parse_route("" if _blank(row.get("Pfad")) else str(row.get("Pfad")))
        if any(node_key(n) in keys for n in path_nodes):
            kid = _kabelnr(row)
            if kid:
                hit.add(kid)
    return hit


def area_cable_ids(summary: dict) -> set[str]:
    return {str(x) for x in summary.get("cable_ids") or [] if x}


def remaining_cable_ids(summary: dict, *, min_remaining_m: float = 0.0) -> list[str]:
    """Kabelnr list for cables that still have remaining meters in this area (paste order)."""
    out: list[str] = []
    seen: set[str] = set()
    for _row, info in summary.get("cable_infos") or []:
        rem = float(info.get("remaining_m") or 0.0)
        if rem <= min_remaining_m:
            continue
        kid = str(info.get("kabelnr") or "").strip()
        if not kid or kid in seen:
            continue
        seen.add(kid)
        out.append(kid)
    return out


def remaining_cables_frame(summary: dict, df: pd.DataFrame, *, min_remaining_m: float = 0.0) -> pd.DataFrame:
    """
    Joined-cable rows for cables with remaining pull meters in this area.
    Suitable for Kurzliste / CaTra export.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    ids = remaining_cable_ids(summary, min_remaining_m=min_remaining_m)
    if not ids:
        return df.iloc[0:0].copy()
    id_col = "Kabelnr" if "Kabelnr" in df.columns else None
    if id_col is None:
        return df.iloc[0:0].copy()
    wanted = {str(x) for x in ids}
    part = df[df[id_col].astype(str).isin(wanted)].copy()
    # Keep request/summary order
    order = {kid: i for i, kid in enumerate(ids)}
    part["_rem_ord"] = part[id_col].astype(str).map(lambda k: order.get(k, 10**9))
    part = part.sort_values("_rem_ord").drop(columns=["_rem_ord"]).reset_index(drop=True)
    rem_map = {str(info["kabelnr"]): info for _row, info in (summary.get("cable_infos") or [])}
    part["Area_remaining_m"] = part[id_col].astype(str).map(
        lambda k: float(rem_map.get(k, {}).get("remaining_m") or 0.0)
    )
    return part


def blocked_entity_cables(
    entity: str,
    areas: list[AreaDef],
    df: pd.DataFrame,
) -> set[str]:
    """entity: 'area:<key>' | 'tray:<id>' | 'pen:<id>'."""
    if entity.startswith("area:"):
        key = entity[5:]
        area = next((a for a in areas if a.key == key), None)
        if area is None:
            return set()
        return cables_hitting_nodes(df, area.nodes)
    if entity.startswith("tray:"):
        return cables_hitting_nodes(df, [entity[5:]])
    if entity.startswith("pen:"):
        return cables_hitting_nodes(df, [entity[4:]])
    return set()


def affected_areas(
    entity: str,
    areas: list[AreaDef],
    summaries: list[dict],
    df: pd.DataFrame,
) -> list[AreaDef]:
    blocked_cables = blocked_entity_cables(entity, areas, df)
    if not blocked_cables:
        return []
    source_key = entity[5:] if entity.startswith("area:") else None
    out: list[AreaDef] = []
    for summary in summaries:
        area = summary["area"]
        if source_key is not None and area.key == source_key:
            continue
        if area_cable_ids(summary) & blocked_cables:
            out.append(area)
    return out


def totals_from_summaries(
    summaries: list[dict],
    *,
    pullers: float = DEFAULT_PULLERS,
    hours_per_week: float = DEFAULT_HOURS_PER_WEEK,
    as_of: date | None = None,
) -> dict:
    as_of = as_of or date.today()
    hours = sum(float(s.get("person_hours") or 0.0) for s in summaries)
    rem_thin = sum(float(s.get("remaining_thin_m") or 0.0) for s in summaries)
    rem_thick = sum(float(s.get("remaining_thick_m") or 0.0) for s in summaries)
    cables = sum(int(s.get("cables") or 0) for s in summaries)
    pulled = sum(int(s.get("pulled") or 0) for s in summaries)

    end_dates = [
        sch["end_date"]
        for s in summaries
        for sch in (s.get("schedule") or {},)
        if sch.get("end_date") is not None
    ]
    if end_dates:
        last = max(end_dates)
        any_work = any(int((s.get("schedule") or {}).get("workdays") or 0) > 0 for s in summaries)
        if not any_work:
            last = as_of
            workdays = 0
        else:
            workdays = 0
            d = as_of
            while d <= last:
                if d.weekday() < 5:
                    workdays += 1
                d += timedelta(days=1)
        schedule = {
            "person_hours": hours,
            "weekly_capacity": float(pullers) * float(hours_per_week),
            "daily_capacity": (
                (float(pullers) * float(hours_per_week)) / 5.0
                if pullers and hours_per_week
                else 0.0
            ),
            "workdays": workdays,
            "start_date": as_of,
            "end_date": last,
            "kw": kw_label(last),
        }
    else:
        schedule = estimate_schedule(
            hours,
            pullers=pullers,
            hours_per_week=hours_per_week,
            as_of=as_of,
        )
        schedule["start_date"] = as_of

    return {
        "cables": cables,
        "pulled": pulled,
        "pulled_pct": (100.0 * pulled / cables) if cables else 100.0,
        "remaining_thin_m": rem_thin,
        "remaining_thick_m": rem_thick,
        "remaining_m": rem_thin + rem_thick,
        "person_hours": hours,
        "schedule": schedule,
    }
