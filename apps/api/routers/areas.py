from __future__ import annotations

import json
from datetime import date
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import AreasSettings, User
from apps.api.services import dataset as ds
from apps.api.services.areas_cache import clear_areas_cache, compute_scheduled_summaries
from apps.api.services.areas_store import areas_to_payload, load_areas
from apps.api.services.jsonutil import records as json_records
from src.areas import (
    DEFAULT_HOURS_PER_WEEK,
    DEFAULT_H_PER_STUETZE,
    DEFAULT_MAX_PER_ROOM,
    DEFAULT_PULLERS,
    DEFAULT_THICK_PACE,
    DEFAULT_THIN_PACE,
    area_cables_frame,
    areas_node_catalog,
    parse_areas_excel,
    remaining_cables_frame,
)
from src.export import safe_filename
from src.stutzen_filter import (
    DEFAULT_EXPORT_COLUMNS,
    export_column_catalog,
    select_export_columns,
)

router = APIRouter(prefix="/areas", tags=["areas"])

_AREAS_PATH = "areas.json"


class AreasPlan(BaseModel):
    thin_pace: float = DEFAULT_THIN_PACE
    thick_pace: float = DEFAULT_THICK_PACE
    h_per_stuetze: float = DEFAULT_H_PER_STUETZE
    pullers: int = 25  # shared pool (docs / Streamlit planning bar default in practice)
    max_per_room: int = DEFAULT_MAX_PER_ROOM
    hours_per_week: float = DEFAULT_HOURS_PER_WEEK
    priority: dict[str, int] = Field(default_factory=dict)
    installed: dict[str, list[str]] = Field(default_factory=dict)
    blocks: list[str] = Field(default_factory=list)


def _areas_file() -> list:
    areas, source = load_areas(settings.appdata_path)
    if not areas:
        raise HTTPException(
            status_code=404,
            detail="No areas data — bundled default missing and nothing uploaded",
        )
    return areas


def _load_plan(db: Session) -> AreasPlan:
    row = db.query(AreasSettings).first()
    if not row:
        return AreasPlan()
    try:
        payload = json.loads(row.payload_json or "{}")
    except json.JSONDecodeError:
        return AreasPlan()
    return AreasPlan(**{k: v for k, v in payload.items() if k in AreasPlan.model_fields})


def _sum_row(s: dict) -> dict:
    area = s["area"]
    sch = s.get("schedule") or {}
    cables = int(s.get("cables") or 0)
    pulled = int(s.get("pulled") or 0)
    return {
        "key": area.key,
        "name": area.name,
        "deck": area.deck,
        "area_ids": area.area_ids,
        "cables": cables,
        "pulled": pulled,
        "remaining_cables": max(cables - pulled, 0),
        "thick": s.get("thick"),
        "thin": s.get("thin"),
        "through": s.get("through"),
        "terminate": s.get("terminate"),
        "stop": s.get("stop"),
        "pulled_pct": round(float(s.get("pulled_pct") or 0), 1),
        "remaining_m": round(float(s.get("remaining_m") or 0), 1),
        "remaining_thin_m": round(float(s.get("remaining_thin_m") or 0), 1),
        "remaining_thick_m": round(float(s.get("remaining_thick_m") or 0), 1),
        "person_hours": round(float(s.get("person_hours") or 0), 1),
        "crew": int(s.get("crew") or 0),
        "queue_rank": s.get("queue_rank"),
        "zero_person_hours": round(float(s.get("zero_person_hours") or 0), 1),
        "zero_weeks": round(float(s.get("zero_weeks") or 0), 2),
        "thick_through": s.get("thick_through"),
        "thin_through": s.get("thin_through"),
        "thick_terminate": s.get("thick_terminate"),
        "thin_terminate": s.get("thin_terminate"),
        "start_date": sch.get("start_date").isoformat() if sch.get("start_date") else None,
        "end_date": sch.get("end_date").isoformat() if sch.get("end_date") else None,
        "kw": sch.get("kw"),
        "workdays": sch.get("workdays"),
        "priority": None,
    }


def _find_summary(summaries: list[dict], key: str) -> dict:
    for s in summaries:
        if s["area"].key == key:
            return s
    raise HTTPException(status_code=404, detail="Area not found")


def _stuetzen_payload(summary: dict) -> list[dict]:
    rows = []
    for row in summary.get("stuetzen") or []:
        rows.append(
            {
                "stuetze": row.get("stuetze"),
                "cables": int(row.get("cables") or 0),
                "done": int(row.get("done") or 0),
                "pct": round(float(row.get("pct") or 0), 1),
                "complete": bool(row.get("complete")),
            }
        )
    return rows


class AreaCablesExportBody(BaseModel):
    key: str
    columns: list[str] = Field(default_factory=lambda: list(DEFAULT_EXPORT_COLUMNS))
    remaining_only: bool = False


def _compute_summaries(
    db: Session,
    *,
    thin_pace: float | None = None,
    thick_pace: float | None = None,
    h_per_stuetze: float | None = None,
    pullers: int | None = None,
    max_per_room: int | None = None,
    hours_per_week: float | None = None,
    as_of: date | None = None,
) -> tuple[list[dict], dict, AreasPlan]:
    plan = _load_plan(db)
    if ds.load_joined(db) is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    # Ensure bundled/uploaded areas exist (keeps previous 404 semantics for empty installs).
    _areas_file()
    as_of = as_of or date.today()
    thin = float(thin_pace if thin_pace is not None else plan.thin_pace)
    thick = float(thick_pace if thick_pace is not None else plan.thick_pace)
    h_st = float(h_per_stuetze if h_per_stuetze is not None else plan.h_per_stuetze)
    pull = int(pullers if pullers is not None else plan.pullers)
    max_room = int(max_per_room if max_per_room is not None else plan.max_per_room)
    hours = float(hours_per_week if hours_per_week is not None else plan.hours_per_week)
    summaries, totals = compute_scheduled_summaries(
        db,
        thin_pace=thin,
        thick_pace=thick,
        h_per_stuetze=h_st,
        pullers=pull,
        max_per_room=max_room,
        hours_per_week=hours,
        installed=plan.installed,
        priority_map={k: int(v) for k, v in (plan.priority or {}).items()},
        as_of=as_of,
    )
    if not summaries:
        raise HTTPException(status_code=404, detail="No areas data — bundled default missing and nothing uploaded")
    return summaries, totals, plan


@router.get("/list")
def list_areas(
    _: User = Depends(require_roles("planner", "admin", "worker")),
):
    """Area names + Bahn / Stütze nodes for one-click insert into Stützen filter."""
    areas, source = load_areas(settings.appdata_path)
    catalog = areas_node_catalog(areas)
    return {"areas": catalog, "count": len(catalog), "source": source}


@router.post("/upload")
async def upload_areas(
    file: UploadFile = File(...),
    _: User = Depends(require_roles("planner", "admin")),
):
    path = settings.appdata_path / "uploads" / "areas.xlsx"
    path.write_bytes(await file.read())
    try:
        areas = parse_areas_excel(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = areas_to_payload(areas)
    (settings.appdata_path / "datasets" / _AREAS_PATH).write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    clear_areas_cache()
    return {"ok": True, "count": len(payload), "source": "upload"}


@router.get("/settings")
def get_areas_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    return _load_plan(db).model_dump()


@router.put("/settings")
def save_areas_settings(
    body: AreasPlan,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    prev = _load_plan(db)
    row = db.query(AreasSettings).first()
    payload = body.model_dump()
    if not row:
        row = AreasSettings(payload_json=json.dumps(payload))
        db.add(row)
    else:
        row.payload_json = json.dumps(payload)
    db.commit()
    # Heavy cache depends on pace + installed; priority/pullers only need reschedule.
    heavy_changed = (
        float(prev.thin_pace) != float(body.thin_pace)
        or float(prev.thick_pace) != float(body.thick_pace)
        or float(prev.h_per_stuetze) != float(body.h_per_stuetze)
        or (prev.installed or {}) != (body.installed or {})
    )
    if heavy_changed:
        clear_areas_cache()
    return {"ok": True}


@router.get("/summaries")
def area_summaries(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
    thin_pace: float | None = None,
    thick_pace: float | None = None,
    h_per_stuetze: float | None = None,
    pullers: int | None = None,
    max_per_room: int | None = None,
    hours_per_week: float | None = None,
):
    summaries, totals, plan = _compute_summaries(
        db,
        thin_pace=thin_pace,
        thick_pace=thick_pace,
        h_per_stuetze=h_per_stuetze,
        pullers=pullers,
        max_per_room=max_per_room,
        hours_per_week=hours_per_week,
    )
    sch = totals.get("schedule") or {}
    prio = {str(k): int(v) for k, v in (plan.priority or {}).items()}
    rows = []
    for s in summaries:
        row = _sum_row(s)
        row["priority"] = prio.get(row["key"])
        rows.append(row)
    return {
        "plan": plan.model_dump(),
        "summaries": rows,
        "totals": {
            "person_hours": round(float(totals.get("person_hours") or 0), 1),
            "remaining_m": round(float(totals.get("remaining_m") or 0), 1),
            "cables": totals.get("cables"),
            "pulled_pct": round(float(totals.get("pulled_pct") or 0), 1),
            "schedule": {
                "kw": sch.get("kw"),
                "workdays": sch.get("workdays"),
                "start_date": sch.get("start_date").isoformat() if sch.get("start_date") else None,
                "end_date": sch.get("end_date").isoformat() if sch.get("end_date") else None,
            },
        },
    }


@router.get("/export-columns")
def area_export_columns(_: User = Depends(require_roles("planner", "admin"))):
    return {"columns": export_column_catalog(), "defaults": list(DEFAULT_EXPORT_COLUMNS)}


@router.get("/detail")
def area_detail(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
    key: str = Query(..., min_length=1),
):
    summaries, _totals, plan = _compute_summaries(db)
    summary = _find_summary(summaries, key.strip())
    area = summary["area"]
    row = _sum_row(summary)
    row["priority"] = (plan.priority or {}).get(area.key)
    joined = ds.load_joined(db)
    preview_frame = area_cables_frame(summary, joined) if joined is not None else pd.DataFrame()
    preview_cols = [
        c
        for c in ("Kabelnr", "Liste", "Category", "Length_m", "Pull_status", "Geraet_A", "Geraet_E")
        if c in preview_frame.columns
    ]
    preview = json_records(preview_frame[preview_cols].head(80)) if preview_cols else []
    remaining_n = len(remaining_cables_frame(summary, joined)) if joined is not None else 0
    pulled = int(row.get("pulled") or 0)
    remaining_cables = int(row.get("remaining_cables") or 0)
    return {
        "summary": row,
        "area": {
            "key": area.key,
            "name": area.name,
            "deck": area.deck,
            "area_ids": area.area_ids,
            "trays": list(area.trays),
            "penetrations": list(area.penetrations),
        },
        "stuetzen": _stuetzen_payload(summary),
        "preview": preview,
        "cable_count": int(row.get("cables") or 0),
        "remaining_cable_count": remaining_n,
        "charts": {
            "pulled_vs_remaining": [
                {"name": "Behúzott", "value": pulled},
                {"name": "Hátralévő", "value": remaining_cables},
            ],
            "thick_thin": [
                {"name": "Thick", "value": int(row.get("thick") or 0)},
                {"name": "Thin", "value": int(row.get("thin") or 0)},
            ],
            "roles": [
                {"name": "Through", "value": int(row.get("through") or 0)},
                {"name": "Terminate", "value": int(row.get("terminate") or 0)},
                {"name": "Stop", "value": int(row.get("stop") or 0)},
            ],
            "remaining_m": [
                {"name": "Thin m", "value": float(row.get("remaining_thin_m") or 0)},
                {"name": "Thick m", "value": float(row.get("remaining_thick_m") or 0)},
            ],
        },
    }


@router.post("/export-cables")
def export_area_cables(
    body: AreaCablesExportBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    summaries, _totals, _plan = _compute_summaries(db)
    summary = _find_summary(summaries, body.key.strip())
    joined = ds.load_joined(db)
    if joined is None or joined.empty:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    frame = (
        remaining_cables_frame(summary, joined)
        if body.remaining_only
        else area_cables_frame(summary, joined)
    )
    if frame.empty:
        raise HTTPException(status_code=404, detail="No matching cables")
    slim = select_export_columns(frame, body.columns)
    data = ds.export_table(slim, sheet="AreaCables")
    area = summary["area"]
    stem = safe_filename(f"area_{area.name}_{area.deck}" + ("_remaining" if body.remaining_only else ""))
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{stem}.xlsx"'},
    )


@router.get("/export")
def export_areas(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
    thin_pace: float | None = None,
    thick_pace: float | None = None,
    h_per_stuetze: float | None = None,
    pullers: int | None = None,
    max_per_room: int | None = None,
    hours_per_week: float | None = None,
):
    """Excel: Overview + FromZero sheets (Streamlit Areas tables)."""
    summaries, totals, _plan = _compute_summaries(
        db,
        thin_pace=thin_pace,
        thick_pace=thick_pace,
        h_per_stuetze=h_per_stuetze,
        pullers=pullers,
        max_per_room=max_per_room,
        hours_per_week=hours_per_week,
    )
    rows = [_sum_row(s) for s in summaries]
    overview = pd.DataFrame(
        [
            {
                "Area": r["name"],
                "Deck": r["deck"],
                "ID": r["area_ids"],
                "Cables": r["cables"],
                "Thick": r["thick"],
                "Thin": r["thin"],
                "Through": r["through"],
                "Terminate": r["terminate"],
                "Stops": r["stop"],
                "Pulled %": r["pulled_pct"],
                "Remaining m": r["remaining_m"],
                "Person-hours": r["person_hours"],
                "Crew": r["crew"],
                "Start": r["start_date"] or "",
                "Workdays": r["workdays"],
                "KW": r["kw"],
            }
            for r in rows
        ]
    )
    from_zero = pd.DataFrame(
        [
            {
                "Area": r["name"],
                "Deck": r["deck"],
                "Through thick": r["thick_through"],
                "Through thin": r["thin_through"],
                "Terminate thick": r["thick_terminate"],
                "Terminate thin": r["thin_terminate"],
                "From-zero hours": r["zero_person_hours"],
                "Weeks (≤5/room)": r["zero_weeks"],
            }
            for r in rows
        ]
    )
    totals_row = pd.DataFrame(
        [
            {
                "Person-hours": round(float(totals.get("person_hours") or 0), 1),
                "Remaining m": round(float(totals.get("remaining_m") or 0), 1),
                "Cables": totals.get("cables"),
                "Pulled %": round(float(totals.get("pulled_pct") or 0), 1),
                "KW": (totals.get("schedule") or {}).get("kw"),
                "Workdays": (totals.get("schedule") or {}).get("workdays"),
                "End": (
                    (totals.get("schedule") or {}).get("end_date").isoformat()
                    if (totals.get("schedule") or {}).get("end_date")
                    else ""
                ),
            }
        ]
    )
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        overview.to_excel(writer, index=False, sheet_name="Overview")
        from_zero.to_excel(writer, index=False, sheet_name="FromZero")
        totals_row.to_excel(writer, index=False, sheet_name="Totals")
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="areas_export.xlsx"'},
    )
