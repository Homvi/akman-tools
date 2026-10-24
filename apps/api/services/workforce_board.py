from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from apps.api.config import settings

_WF_PATH = "workforce.parquet"
_BOARD_PATH = "workforce_board.json"
_INACTIVE_DAYS = 21

_LEAD_RE = re.compile(
    r"(team\s*lead|csoportvezet|group\s*lead|vorarbeiter|\blead\b|leiter)",
    re.IGNORECASE,
)


def workforce_parquet_path() -> Path:
    return settings.appdata_path / "datasets" / _WF_PATH


def board_path() -> Path:
    return settings.appdata_path / "datasets" / _BOARD_PATH


def is_team_lead(position: str) -> bool:
    return bool(_LEAD_RE.search(str(position or "")))


def _empty_board() -> dict[str, Any]:
    return {
        "tasks": [],
        "updated_at": None,
    }


def load_workforce_frame() -> pd.DataFrame | None:
    path = workforce_parquet_path()
    if not path.exists():
        return None
    return pd.read_parquet(path)


def ensure_workforce_status(frame: pd.DataFrame | None = None) -> pd.DataFrame | None:
    """Re-parse uploaded Excel once if Status column is missing (leave hints)."""
    current = frame if frame is not None else load_workforce_frame()
    if current is not None and not current.empty and "Status" in current.columns:
        return current
    upload = settings.appdata_path / "uploads" / "workforce.xlsx"
    if not upload.exists():
        return current
    try:
        from src.workforce import parse_workforce_excel

        year = date.today().year
        if current is not None and not current.empty and "Date" in current.columns:
            try:
                year = int(pd.to_datetime(current["Date"], errors="coerce").dropna().dt.year.mode().iloc[0])
            except Exception:
                pass
        refreshed = parse_workforce_excel(upload, year=year)
        out = workforce_parquet_path()
        out.parent.mkdir(parents=True, exist_ok=True)
        refreshed.to_parquet(out, index=False)
        return refreshed
    except Exception:
        return current


def _clean_name(value: Any) -> str:
    name = str(value or "").strip()
    if not name or name.lower() in {"nan", "<na>", "none"}:
        return ""
    return name


def _clean_position(value: Any) -> str:
    position = " ".join(str(value or "").split())
    if position.lower() in {"nan", "<na>", "none"}:
        return ""
    return position


def _canonical_positions(raw_positions: list[str]) -> dict[str, str]:
    """Map casefold(position) -> most common display spelling."""
    counts: dict[str, dict[str, int]] = {}
    for pos in raw_positions:
        cleaned = _clean_position(pos)
        if not cleaned:
            continue
        key = cleaned.casefold()
        bucket = counts.setdefault(key, {})
        bucket[cleaned] = bucket.get(cleaned, 0) + 1
    out: dict[str, str] = {}
    for key, spellings in counts.items():
        out[key] = max(spellings.items(), key=lambda item: (item[1], -len(item[0]), item[0]))[0]
    return out


def _is_present_cell(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "x"}


def staffing_as_of(frame: pd.DataFrame, *, today: date | None = None) -> date | None:
    """Pick the day used for available / on-leave flags.

    Prefer calendar today when it falls inside the Excel range; otherwise the
    latest day that still has someone present (ignores empty future columns).
    """
    if frame is None or frame.empty or "Date" not in frame.columns:
        return None
    dates = pd.to_datetime(frame["Date"], errors="coerce").dropna()
    if dates.empty:
        return None
    min_d = dates.min().date()
    max_d = dates.max().date()
    day = today or date.today()
    if min_d <= day <= max_d:
        return day
    if "Present" in frame.columns:
        present = frame.copy()
        present["Date"] = pd.to_datetime(present["Date"], errors="coerce")
        present = present.dropna(subset=["Date"])
        mask = present["Present"].map(_is_present_cell)
        with_people = present.loc[mask, "Date"]
        if not with_people.empty:
            return with_people.max().date()
    return max_d


def _leave_window(
    person_rows: pd.DataFrame,
    *,
    from_day: date,
) -> tuple[date | None, date | None]:
    """Next leave start/end (inclusive) on/after from_day from Status==leave."""
    if person_rows.empty or "Status" not in person_rows.columns:
        return None, None
    leave = person_rows.copy()
    leave["Date"] = pd.to_datetime(leave["Date"], errors="coerce")
    leave = leave.dropna(subset=["Date"])
    leave = leave[leave["Status"].astype(str).str.lower().eq("leave")]
    leave = leave[leave["Date"].dt.date >= from_day].sort_values("Date")
    if leave.empty:
        return None, None
    start = leave.iloc[0]["Date"].date()
    end = start
    for ts in leave["Date"].dt.date.tolist()[1:]:
        if ts == end + timedelta(days=1):
            end = ts
            continue
        break
    return start, end


def _bridges_weekend(prev_end: date, nxt: date) -> bool:
    """True when only Saturday/Sunday lie between prev_end and nxt."""
    gap = prev_end + timedelta(days=1)
    while gap < nxt:
        if gap.weekday() < 5:
            return False
        gap += timedelta(days=1)
    return True


def _leave_ranges(person_rows: pd.DataFrame, *, from_day: date) -> list[dict[str, str]]:
    """All continuous leave blocks (weekends bridged) that end on/after from_day."""
    if person_rows.empty or "Status" not in person_rows.columns:
        return []
    leave = person_rows.copy()
    leave["Date"] = pd.to_datetime(leave["Date"], errors="coerce")
    leave = leave.dropna(subset=["Date"])
    leave = leave[leave["Status"].astype(str).str.lower().eq("leave")]
    days = sorted({ts.date() for ts in leave["Date"]})
    blocks: list[tuple[date, date]] = []
    for d in days:
        if blocks and _bridges_weekend(blocks[-1][1], d):
            blocks[-1] = (blocks[-1][0], d)
        else:
            blocks.append((d, d))
    return [
        {"start": start.isoformat(), "end": end.isoformat()}
        for start, end in blocks
        if end >= from_day
    ]


def list_people(
    df: pd.DataFrame | None = None,
    *,
    as_of: date | None = None,
    inactive_days: int = _INACTIVE_DAYS,
) -> list[dict[str, Any]]:
    """Unique people from workforce Excel (latest position wins).

    Drops anyone whose last logged work day is older than ``inactive_days``
    before the staffing day. Adds next leave window when Status is available.
    """
    frame = ensure_workforce_status(df if df is not None else load_workforce_frame())
    if frame is None or frame.empty or "Name" not in frame.columns:
        return []

    view = frame.copy()
    view["Name"] = view["Name"].map(_clean_name)
    view = view[view["Name"] != ""]
    if view.empty:
        return []

    if "Date" in view.columns:
        view["Date"] = pd.to_datetime(view["Date"], errors="coerce")
        view = view.dropna(subset=["Date"])
    else:
        return []

    if "Position" in view.columns:
        view["Position"] = view["Position"].map(_clean_position)
    else:
        view["Position"] = ""

    # Collapse "Iron worker" / "Iron Worker" (and similar) into one chip label.
    canon = _canonical_positions(view["Position"].tolist())
    view["Position"] = view["Position"].map(lambda p: canon.get(str(p).casefold(), p) if p else "")

    day = as_of or staffing_as_of(view)
    if day is None:
        return []
    day_ts = pd.Timestamp(day).normalize()
    cutoff = day_ts - pd.Timedelta(days=int(inactive_days))

    present_mask = view["Present"].map(_is_present_cell) if "Present" in view.columns else pd.Series(False, index=view.index)
    last_present = (
        view.loc[present_mask]
        .groupby(view.loc[present_mask, "Name"].str.casefold())["Date"]
        .max()
    )

    present_names: set[str] = set()
    day_rows = view[view["Date"].dt.normalize().eq(day_ts)]
    for _, row in day_rows.iterrows():
        if _is_present_cell(row.get("Present")):
            present_names.add(str(row["Name"]))

    # Latest position: walk newest → oldest
    newest_first = view.sort_values("Date", ascending=False)
    people: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, row in newest_first.iterrows():
        name = str(row["Name"])
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)

        last = last_present.get(key)
        if last is None or pd.isna(last) or pd.Timestamp(last) < cutoff:
            continue

        position = str(row.get("Position") or "")
        available = name in present_names
        person_rows = view[view["Name"].str.casefold() == key]
        leave_start, leave_end = _leave_window(person_rows, from_day=day)
        leave_ranges = _leave_ranges(person_rows, from_day=day)
        on_leave_now = False
        if leave_start and leave_end and leave_start <= day <= leave_end:
            on_leave_now = True
        elif not available and "Status" in day_rows.columns:
            person_today = day_rows[day_rows["Name"].str.casefold() == key]
            if not person_today.empty and str(person_today.iloc[0].get("Status") or "").lower() == "leave":
                on_leave_now = True

        people.append(
            {
                "id": name,
                "name": name,
                "position": position,
                "is_lead": is_team_lead(position),
                "available": available and not on_leave_now,
                "on_leave": on_leave_now,
                "last_present": pd.Timestamp(last).date().isoformat(),
                "leave_start": leave_start.isoformat() if leave_start else None,
                "leave_end": leave_end.isoformat() if leave_end else None,
                "leave_ranges": leave_ranges,
                "as_of": day.isoformat(),
            }
        )
    people.sort(
        key=lambda p: (
            p.get("on_leave", False),
            not p["is_lead"],
            p["position"].casefold(),
            p["name"].casefold(),
        )
    )
    return people


def unique_positions_from_people(people: list[dict[str, Any]]) -> list[str]:
    return sorted({p["position"] for p in people if p.get("position")}, key=str.casefold)


def load_board() -> dict[str, Any]:
    path = board_path()
    if not path.exists():
        return _empty_board()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_board()
    if not isinstance(data, dict):
        return _empty_board()
    return normalize_board(data)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _parse_size(value: Any) -> int:
    try:
        size = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, min(size, 999))


_BLOCKER_NOTE_MAX = 500


def _parse_iso_day(value: Any) -> date | None:
    if value in (None, "", "null"):
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _parse_date_range(item: dict[str, Any]) -> tuple[str | None, str | None]:
    start = _parse_iso_day(item.get("start_date"))
    end = _parse_iso_day(item.get("end_date"))
    if start and end and end < start:
        start, end = end, start
    return (start.isoformat() if start else None, end.isoformat() if end else None)


def _parse_blocker_note(value: Any) -> str:
    return str(value or "").strip()[:_BLOCKER_NOTE_MAX]


def _migrate_legacy_board(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Old model: teams + person→team assignments + nested checklist tasks."""
    teams_in = raw.get("teams") if isinstance(raw.get("teams"), list) else []
    assignments_in = raw.get("assignments") if isinstance(raw.get("assignments"), dict) else {}
    tasks_in = raw.get("tasks") if isinstance(raw.get("tasks"), list) else []

    by_team: dict[str, list[str]] = {}
    for person_id, team_id in assignments_in.items():
        pid = str(person_id or "").strip()
        tid = None if team_id in (None, "", "null") else str(team_id).strip()
        if not pid or not tid:
            continue
        by_team.setdefault(tid, []).append(pid)

    for item in tasks_in:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("team_id") or "").strip()
        if not tid:
            continue
        for aid in item.get("assignee_ids") or []:
            pid = str(aid or "").strip()
            if pid and pid not in by_team.get(tid, []):
                by_team.setdefault(tid, []).append(pid)

    out: list[dict[str, Any]] = []
    for i, item in enumerate(teams_in):
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id") or "").strip() or _new_id("task")
        title = str(item.get("name") or "").strip() or f"Task {i + 1}"
        members = list(by_team.get(tid, []))
        lead_id = None
        workers: list[str] = []
        for pid in members:
            # Heuristic: first person stays lead only if marked later on UI;
            # migration keeps all as workers unless single member.
            workers.append(pid)
        if workers and len(workers) == 1:
            lead_id = workers.pop(0)
        out.append(
            {
                "id": tid if tid.startswith("task_") else _new_id("task"),
                "title": title,
                "size": _parse_size(item.get("size")),
                "lead_id": lead_id,
                "worker_ids": workers,
                "blocker": False,
                "done": False,
                "order": i,
            }
        )

    # Standalone old checklist tasks without a matching team → own columns
    team_ids = {str(t.get("id") or "") for t in teams_in if isinstance(t, dict)}
    for i, item in enumerate(tasks_in):
        if not isinstance(item, dict):
            continue
        team_id = str(item.get("team_id") or "").strip()
        if team_id in team_ids:
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        workers = []
        for aid in item.get("assignee_ids") or []:
            pid = str(aid or "").strip()
            if pid and pid not in workers:
                workers.append(pid)
        out.append(
            {
                "id": str(item.get("id") or "").strip() or _new_id("task"),
                "title": title,
                "size": _parse_size(item.get("size")),
                "lead_id": None,
                "worker_ids": workers,
                "blocker": bool(item.get("blocker")),
                "done": bool(item.get("done")),
                "order": len(out) + i,
            }
        )
    return out


def normalize_board(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Task-centric board: each task has one lead + workers (no teams)."""
    raw = payload if isinstance(payload, dict) else {}
    tasks_in = raw.get("tasks") if isinstance(raw.get("tasks"), list) else []

    looks_new = any(
        isinstance(t, dict)
        and ("lead_id" in t or "worker_ids" in t or not str(t.get("team_id") or "").strip())
        for t in tasks_in
    )
    if not looks_new and (raw.get("teams") or raw.get("assignments")):
        tasks_in = _migrate_legacy_board(raw)

    claimed: set[str] = set()
    tasks: list[dict[str, Any]] = []
    for i, item in enumerate(tasks_in):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        if not title:
            continue
        task_id = str(item.get("id") or "").strip() or _new_id("task")
        try:
            order = int(item.get("order", i))
        except (TypeError, ValueError):
            order = i

        lead_raw = item.get("lead_id")
        lead_id = None if lead_raw in (None, "", "null") else str(lead_raw).strip()
        if lead_id and lead_id in claimed:
            lead_id = None
        if lead_id:
            claimed.add(lead_id)

        workers_src = item.get("worker_ids")
        if not isinstance(workers_src, list):
            # Back-compat: assignee_ids without lead
            workers_src = item.get("assignee_ids") if isinstance(item.get("assignee_ids"), list) else []
        worker_ids: list[str] = []
        for aid in workers_src:
            pid = str(aid or "").strip()
            if not pid or pid in claimed or pid == lead_id:
                continue
            claimed.add(pid)
            worker_ids.append(pid)

        start_date, end_date = _parse_date_range(item)
        tasks.append(
            {
                "id": task_id,
                "title": title,
                "size": _parse_size(item.get("size")),
                "lead_id": lead_id,
                "worker_ids": worker_ids,
                "blocker": bool(item.get("blocker")),
                "blocker_note": _parse_blocker_note(item.get("blocker_note")),
                "done": bool(item.get("done")),
                "start_date": start_date,
                "end_date": end_date,
                "order": order,
            }
        )

    tasks.sort(key=lambda t: (t["order"], t["title"].casefold()))
    return {
        "tasks": tasks,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def save_board(payload: dict[str, Any] | None) -> dict[str, Any]:
    board = normalize_board(payload)
    path = board_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    return board
