from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from apps.api.config import settings
from apps.api.services.person_names import person_key
from src.staffing_categories import normalize_requirements

_WF_PATH = "workforce.parquet"
_BOARD_PATH = "workforce_board.json"

_LEAD_RE = re.compile(
    r"(team\s*lead|csoportvezet|group\s*lead|vorarbeiter|\blead\b|leiter)",
    re.IGNORECASE,
)

# Process-local caches (mtime/size keyed). Cleared on Excel upload / meta writes.
_FRAME_CACHE: dict[str, Any] = {"sig": None, "frame": None}
_PEOPLE_CACHE: dict[str, Any] = {"sig": None, "as_of": None, "people": None, "off_roster": None}


def workforce_parquet_path() -> Path:
    return settings.appdata_path / "datasets" / _WF_PATH


def board_path() -> Path:
    return settings.appdata_path / "datasets" / _BOARD_PATH


def clear_workforce_cache() -> None:
    _FRAME_CACHE["sig"] = None
    _FRAME_CACHE["frame"] = None
    _PEOPLE_CACHE["sig"] = None
    _PEOPLE_CACHE["as_of"] = None
    _PEOPLE_CACHE["people"] = None
    _PEOPLE_CACHE["off_roster"] = None


def ensure_project_column(frame: pd.DataFrame) -> pd.DataFrame:
    """Guarantee a ``Project`` column; missing/blank → main roster (None)."""
    out = frame.copy()
    if "Project" not in out.columns:
        out["Project"] = None
    else:
        out["Project"] = out["Project"].map(
            lambda v: None
            if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in {"", "nan", "None"}
            else str(v).strip()
        )
    return out


def _project_mask(frame: pd.DataFrame, project: str | None) -> pd.Series:
    """Rows belonging to ``project`` (None = main / untagged roster)."""
    col = frame["Project"]
    if project is None:
        return col.isna() | col.astype(str).str.strip().isin({"", "nan", "None"})
    return col.astype(str).str.strip().eq(str(project).strip())


# When the same person+day appears on multiple sheets (e.g. September blank
# October columns vs October ``u`` leave), keep the most informative status.
_STATUS_RANK = {
    "leave": 0,
    "sick": 1,
    "work": 2,
    "off": 3,
    "empty": 4,
}


def dedupe_workforce_days(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per Date + person; prefer leave/work over empty placeholders."""
    if frame is None or frame.empty:
        return frame
    work = frame.copy()
    work["Date"] = pd.to_datetime(work["Date"], errors="coerce")
    work = work.dropna(subset=["Date"])
    if "Name" not in work.columns:
        return work
    work["_ikey"] = work["Name"].map(lambda n: person_key(str(n or "")))
    work = work[work["_ikey"] != ""]
    if work.empty:
        return work.drop(columns=["_ikey"], errors="ignore")
    status = work["Status"].astype(str).str.lower() if "Status" in work.columns else "empty"
    work["_rank"] = status.map(lambda s: _STATUS_RANK.get(str(s), 5))
    # Stable: best status first; then later sheet rows win ties.
    work = work.sort_values(["Date", "_ikey", "_rank"], kind="mergesort")
    work = work.drop_duplicates(subset=["Date", "_ikey"], keep="first")
    return work.drop(columns=["_ikey", "_rank"]).sort_values(["Date", "Position", "Name"]).reset_index(drop=True)


def merge_workforce_upload(
    existing: pd.DataFrame | None,
    incoming: pd.DataFrame,
    *,
    project: str | None,
) -> pd.DataFrame:
    """Replace rows for one project slice; keep all other project slices.

    Dedupes on Date + person identity, preferring leave/work over empty.
    """
    incoming = ensure_project_column(incoming)
    if project:
        incoming = incoming.copy()
        incoming["Project"] = str(project).strip()
    else:
        incoming = incoming.copy()
        incoming["Project"] = None

    if existing is None or existing.empty:
        kept = incoming
    else:
        base = ensure_project_column(existing)
        keep = base.loc[~_project_mask(base, project)]
        kept = pd.concat([keep, incoming], ignore_index=True)

    if kept.empty:
        return kept

    return dedupe_workforce_days(kept)


def _parquet_signature() -> str | None:
    path = workforce_parquet_path()
    if not path.exists():
        return None
    st = path.stat()
    return f"{st.st_mtime_ns}:{st.st_size}"


def is_team_lead(position: str) -> bool:
    return bool(_LEAD_RE.search(str(position or "")))


def _empty_board() -> dict[str, Any]:
    return {
        "tasks": [],
        "updated_at": None,
    }


def load_workforce_frame() -> pd.DataFrame | None:
    sig = _parquet_signature()
    if sig is None:
        clear_workforce_cache()
        return None
    if _FRAME_CACHE["sig"] == sig and _FRAME_CACHE["frame"] is not None:
        return _FRAME_CACHE["frame"]
    frame = ensure_project_column(pd.read_parquet(workforce_parquet_path()))
    # Heal older uploads where blank September day-columns wiped October leave.
    frame = dedupe_workforce_days(frame)
    _FRAME_CACHE["sig"] = sig
    _FRAME_CACHE["frame"] = frame
    # People list depends on the frame; drop stale people cache.
    _PEOPLE_CACHE["sig"] = None
    _PEOPLE_CACHE["people"] = None
    _PEOPLE_CACHE["off_roster"] = None
    return frame


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
        clear_workforce_cache()
        _FRAME_CACHE["sig"] = _parquet_signature()
        _FRAME_CACHE["frame"] = refreshed
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


def _prepare_people_view(frame: pd.DataFrame) -> pd.DataFrame | None:
    """Clean names/dates/positions and attach identity key column ``_ikey``."""
    if frame is None or frame.empty or "Name" not in frame.columns:
        return None
    view = frame.copy()
    view["Name"] = view["Name"].map(_clean_name)
    view = view[view["Name"] != ""]
    if view.empty:
        return None
    if "Date" not in view.columns:
        return None
    view["Date"] = pd.to_datetime(view["Date"], errors="coerce")
    view = view.dropna(subset=["Date"])
    if view.empty:
        return None
    if "Position" in view.columns:
        view["Position"] = view["Position"].map(_clean_position)
    else:
        view["Position"] = ""
    canon = _canonical_positions(view["Position"].tolist())
    view["Position"] = view["Position"].map(lambda p: canon.get(str(p).casefold(), p) if p else "")
    view["_ikey"] = view["Name"].map(person_key)
    view = view[view["_ikey"] != ""]
    return view if not view.empty else None


def canonical_names_from_frame(df: pd.DataFrame | None = None) -> dict[str, str]:
    """Map ``person_key`` → latest display spelling from the workforce frame."""
    frame = ensure_workforce_status(df if df is not None else load_workforce_frame())
    view = _prepare_people_view(frame) if frame is not None else None
    if view is None:
        return {}
    out: dict[str, str] = {}
    for _, row in view.sort_values("Date", ascending=False).iterrows():
        key = str(row["_ikey"])
        if key not in out:
            out[key] = str(row["Name"])
    return out


def remap_board_person_names(
    board: dict[str, Any],
    canonical_by_identity: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Rewrite lead/worker ids to the canonical display name for each identity."""
    canon = canonical_by_identity if canonical_by_identity is not None else canonical_names_from_frame()
    if not canon:
        return board

    def resolve(raw: str | None) -> str | None:
        if raw in (None, ""):
            return None
        text = str(raw).strip()
        if not text:
            return None
        return canon.get(person_key(text), text)

    tasks: list[dict[str, Any]] = []
    for task in board.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        t = dict(task)
        lead = resolve(t.get("lead_id"))
        seen: set[str] = set()
        workers: list[str] = []
        for wid in t.get("worker_ids") or []:
            pid = resolve(str(wid) if wid is not None else None)
            if not pid or pid == lead or pid in seen:
                continue
            seen.add(pid)
            workers.append(pid)
        t["lead_id"] = lead
        t["worker_ids"] = workers
        tasks.append(t)
    return {**board, "tasks": tasks}


def _shift_month(day: date, delta: int) -> date:
    """First day of the calendar month ``delta`` months from ``day``'s month."""
    month_index = day.month - 1 + delta
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _keys_in_calendar_month(view: pd.DataFrame, year: int, month: int) -> set[str]:
    dates = view["Date"]
    mask = (dates.dt.year == year) & (dates.dt.month == month)
    if not mask.any():
        return set()
    return set(view.loc[mask, "_ikey"].astype(str).tolist())


def roster_months(as_of: date) -> tuple[date, date]:
    """Return (current_month_start, next_month_start) for roster membership."""
    current = date(as_of.year, as_of.month, 1)
    return current, _shift_month(as_of, 1)


def _build_people_for_keys(
    view: pd.DataFrame,
    *,
    keys: set[str],
    day: date,
) -> list[dict[str, Any]]:
    """Build person dicts for the given identity keys (latest spelling wins)."""
    if not keys:
        return []

    day_ts = pd.Timestamp(day).normalize()
    present_mask = (
        view["Present"].map(_is_present_cell) if "Present" in view.columns else pd.Series(False, index=view.index)
    )
    last_present = view.loc[present_mask].groupby("_ikey")["Date"].max()

    present_keys: set[str] = set()
    day_rows = view[view["Date"].dt.normalize().eq(day_ts)]
    for _, row in day_rows.iterrows():
        if _is_present_cell(row.get("Present")):
            present_keys.add(str(row["_ikey"]))

    newest_first = view.sort_values("Date", ascending=False)
    people: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, row in newest_first.iterrows():
        key = str(row["_ikey"])
        if key in seen or key not in keys:
            continue
        seen.add(key)

        last = last_present.get(key)
        name = str(row["Name"])
        position = str(row.get("Position") or "")
        available = key in present_keys
        person_rows = view[view["_ikey"] == key]
        leave_start, leave_end = _leave_window(person_rows, from_day=day)
        leave_ranges = _leave_ranges(person_rows, from_day=day)
        on_leave_now = False
        if leave_start and leave_end and leave_start <= day <= leave_end:
            on_leave_now = True
        elif not available and "Status" in day_rows.columns:
            person_today = day_rows[day_rows["_ikey"] == key]
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
                "last_present": (
                    pd.Timestamp(last).date().isoformat()
                    if last is not None and not pd.isna(last)
                    else None
                ),
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


def _people_view_and_day(
    df: pd.DataFrame | None,
    *,
    as_of: date | None,
) -> tuple[pd.DataFrame | None, date | None]:
    frame = ensure_workforce_status(df if df is not None else load_workforce_frame())
    view = _prepare_people_view(frame) if frame is not None else None
    if view is None:
        return None, None
    day = as_of or staffing_as_of(view)
    return view, day


def list_people(
    df: pd.DataFrame | None = None,
    *,
    as_of: date | None = None,
) -> list[dict[str, Any]]:
    """Unique people on the current calendar month's roster (névsor).

    Dedupes by token identity (order-/case-/accent-insensitive). A person is
    included if they have any Excel row in the month of ``as_of`` (or
    ``staffing_as_of``), including leave/empty cells.
    """
    use_cache = df is None
    sig = _parquet_signature() if use_cache else None
    as_of_key = as_of.isoformat() if as_of else None
    if (
        use_cache
        and sig
        and _PEOPLE_CACHE["sig"] == sig
        and _PEOPLE_CACHE["as_of"] == as_of_key
        and _PEOPLE_CACHE["people"] is not None
    ):
        return list(_PEOPLE_CACHE["people"])

    view, day = _people_view_and_day(df, as_of=as_of)
    if view is None or day is None:
        return []

    current_month, _ = roster_months(day)
    keys = _keys_in_calendar_month(view, current_month.year, current_month.month)
    people = _build_people_for_keys(view, keys=keys, day=day)

    if use_cache and sig:
        if _PEOPLE_CACHE["sig"] != sig or _PEOPLE_CACHE["as_of"] != as_of_key:
            _PEOPLE_CACHE["off_roster"] = None
        _PEOPLE_CACHE["sig"] = sig
        _PEOPLE_CACHE["as_of"] = as_of_key
        _PEOPLE_CACHE["people"] = people
    return people


def list_off_roster_people(
    df: pd.DataFrame | None = None,
    *,
    as_of: date | None = None,
) -> list[dict[str, Any]]:
    """People who appear in the Excel but not in the current or next month roster."""
    use_cache = df is None
    sig = _parquet_signature() if use_cache else None
    as_of_key = as_of.isoformat() if as_of else None
    if (
        use_cache
        and sig
        and _PEOPLE_CACHE["sig"] == sig
        and _PEOPLE_CACHE["as_of"] == as_of_key
        and _PEOPLE_CACHE["off_roster"] is not None
    ):
        return list(_PEOPLE_CACHE["off_roster"])

    view, day = _people_view_and_day(df, as_of=as_of)
    if view is None or day is None:
        return []

    current_month, next_month = roster_months(day)
    current_keys = _keys_in_calendar_month(view, current_month.year, current_month.month)
    next_keys = _keys_in_calendar_month(view, next_month.year, next_month.month)
    all_keys = set(view["_ikey"].astype(str).tolist())
    off_keys = all_keys - current_keys - next_keys
    people = _build_people_for_keys(view, keys=off_keys, day=day)

    if use_cache and sig:
        # Keep people cache in sync when both are filled via separate calls.
        if _PEOPLE_CACHE["sig"] != sig or _PEOPLE_CACHE["as_of"] != as_of_key:
            _PEOPLE_CACHE["sig"] = sig
            _PEOPLE_CACHE["as_of"] = as_of_key
            _PEOPLE_CACHE["people"] = None
        _PEOPLE_CACHE["off_roster"] = people
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
    return remap_board_person_names(normalize_board(data))


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
        # Lead may count toward headcount / appear among workers on at most one task.
        lead_counts = bool(item.get("lead_counts")) and bool(lead_id)

        # Same person may lead several tasks. Within one task: unique workers;
        # lead is listed in worker_ids only when lead_counts is set.
        workers_src = item.get("worker_ids")
        if not isinstance(workers_src, list):
            # Back-compat: assignee_ids without lead
            workers_src = item.get("assignee_ids") if isinstance(item.get("assignee_ids"), list) else []
        seen_workers: set[str] = set()
        worker_ids: list[str] = []
        for aid in workers_src:
            pid = str(aid or "").strip()
            if not pid or pid in seen_workers:
                continue
            if pid == lead_id and not lead_counts:
                continue
            seen_workers.add(pid)
            worker_ids.append(pid)
        if lead_counts and lead_id and lead_id not in seen_workers:
            worker_ids.append(lead_id)

        start_date, end_date = _parse_date_range(item)
        requirements = normalize_requirements(item.get("requirements"))
        tasks.append(
            {
                "id": task_id,
                "title": title,
                "size": sum(requirements.values()) if requirements else _parse_size(item.get("size")),
                "requirements": requirements,
                "lead_id": lead_id,
                "lead_counts": lead_counts,
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

    # A person may appear in worker_ids of at most one task (first by order wins).
    seen_workers_global: set[str] = set()
    for t in tasks:
        kept: list[str] = []
        for wid in t["worker_ids"]:
            key = str(wid)
            if key in seen_workers_global:
                continue
            seen_workers_global.add(key)
            kept.append(wid)
        t["worker_ids"] = kept
        lid = t.get("lead_id")
        if t.get("lead_counts") and lid and lid not in kept:
            t["lead_counts"] = False

    # A lead can only count on one task — keep the first by order.
    counted_leads: set[str] = set()
    for t in tasks:
        lid = t.get("lead_id")
        if not t.get("lead_counts") or not lid:
            continue
        if lid in counted_leads:
            t["lead_counts"] = False
            t["worker_ids"] = [w for w in t["worker_ids"] if w != lid]
        else:
            counted_leads.add(str(lid))

    return {
        "tasks": tasks,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def save_board(payload: dict[str, Any] | None) -> dict[str, Any]:
    board = remap_board_person_names(normalize_board(payload))
    path = board_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    return board
