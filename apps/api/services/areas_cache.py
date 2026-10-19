from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.services import dataset as ds
from apps.api.services.areas_store import load_areas
from src.areas import schedule_areas, summarize_all_areas, totals_from_summaries

_AREAS_PATH = "areas.json"

# Process-local cache of heavy (pre-schedule) area summaries.
_CACHE: dict[str, Any] = {"key": None, "summaries": None}


def clear_areas_cache() -> None:
    _CACHE["key"] = None
    _CACHE["summaries"] = None


def _areas_fingerprint() -> str:
    path = settings.appdata_path / "datasets" / _AREAS_PATH
    if path.exists():
        st = path.stat()
        return f"upload:{st.st_mtime_ns}:{st.st_size}"
    default_json = Path(__file__).resolve().parents[1] / "defaults" / "areas.json"
    if default_json.exists():
        st = default_json.stat()
        return f"default:{st.st_mtime_ns}:{st.st_size}"
    return "empty"


def _installed_fingerprint(installed: dict | None) -> str:
    raw = json.dumps(installed or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def heavy_cache_key(
    db: Session,
    *,
    thin_pace: float,
    thick_pace: float,
    h_per_stuetze: float,
    installed: dict | None,
) -> str:
    row = ds.current_dataset(db)
    sig = (row.signature if row else "") or "no-dataset"
    return "|".join(
        [
            sig,
            _areas_fingerprint(),
            _installed_fingerprint(installed),
            f"thin={float(thin_pace)}",
            f"thick={float(thick_pace)}",
            f"hst={float(h_per_stuetze)}",
        ]
    )


def _refresh_zero_weeks(summaries: list[dict], *, pullers: float, max_per_room: float, hours_per_week: float) -> None:
    crew_cap = max(min(float(max_per_room or 0), float(pullers or 0)), 0.0)
    room_weekly = crew_cap * float(hours_per_week or 0.0) if crew_cap > 0 else 0.0
    for s in summaries:
        zero_h = float(s.get("zero_person_hours") or 0.0)
        s["zero_weeks"] = (zero_h / room_weekly) if room_weekly > 0 else 0.0


def get_base_summaries(
    db: Session,
    *,
    thin_pace: float,
    thick_pace: float,
    h_per_stuetze: float,
    installed: dict | None,
    pullers: float,
    hours_per_week: float,
    max_per_room: float,
) -> list[dict]:
    """Heavy cable×area aggregation (no pool schedule). Cached in-process."""
    key = heavy_cache_key(
        db,
        thin_pace=thin_pace,
        thick_pace=thick_pace,
        h_per_stuetze=h_per_stuetze,
        installed=installed,
    )
    if _CACHE["key"] == key and _CACHE["summaries"] is not None:
        return _CACHE["summaries"]

    joined = ds.load_joined(db)
    if joined is None:
        return []
    areas, _source = load_areas(settings.appdata_path)
    if not areas:
        return []

    summaries = summarize_all_areas(
        areas,
        joined,
        installed_by_area=installed or {},
        thin_pace=thin_pace,
        thick_pace=thick_pace,
        h_per_stuetze=h_per_stuetze,
        pullers=pullers,
        hours_per_week=hours_per_week,
        max_per_room=max_per_room,
        apply_schedule=False,
    )
    _CACHE["key"] = key
    _CACHE["summaries"] = summaries
    return summaries


def compute_scheduled_summaries(
    db: Session,
    *,
    thin_pace: float,
    thick_pace: float,
    h_per_stuetze: float,
    pullers: float,
    max_per_room: float,
    hours_per_week: float,
    installed: dict | None,
    priority_map: dict[str, int] | None,
    as_of=None,
) -> tuple[list[dict], dict]:
    base = get_base_summaries(
        db,
        thin_pace=thin_pace,
        thick_pace=thick_pace,
        h_per_stuetze=h_per_stuetze,
        installed=installed,
        pullers=pullers,
        hours_per_week=hours_per_week,
        max_per_room=max_per_room,
    )
    # Shallow-copy so schedule mutations do not pollute the cached base.
    summaries = [dict(s) for s in base]
    _refresh_zero_weeks(
        summaries, pullers=pullers, max_per_room=max_per_room, hours_per_week=hours_per_week
    )
    from src.areas import ordered_summaries

    schedule_areas(
        summaries,
        pullers=pullers,
        max_per_room=max_per_room,
        hours_per_week=hours_per_week,
        as_of=as_of,
        priority_map=priority_map,
    )
    summaries = ordered_summaries(summaries, priority_map)
    totals = totals_from_summaries(
        summaries, pullers=pullers, hours_per_week=hours_per_week, as_of=as_of
    )
    return summaries, totals
