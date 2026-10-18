from __future__ import annotations

import json
from datetime import date
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import AreasSettings, User
from apps.api.services import dataset as ds
from src.areas import (
    DEFAULT_HOURS_PER_WEEK,
    DEFAULT_H_PER_STUETZE,
    DEFAULT_MAX_PER_ROOM,
    DEFAULT_PULLERS,
    DEFAULT_THICK_PACE,
    DEFAULT_THIN_PACE,
    AreaDef,
    parse_areas_excel,
    summarize_all_areas,
    totals_from_summaries,
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


def _areas_file() -> list[AreaDef]:
    path = settings.appdata_path / "datasets" / _AREAS_PATH
    if not path.exists():
        raise HTTPException(status_code=404, detail="No areas file — upload Helység Excel first")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [AreaDef(**item) for item in raw]


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
    return {
        "key": area.key,
        "name": area.name,
        "deck": area.deck,
        "area_ids": area.area_ids,
        "cables": s.get("cables"),
        "thick": s.get("thick"),
        "thin": s.get("thin"),
        "through": s.get("through"),
        "terminate": s.get("terminate"),
        "stop": s.get("stop"),
        "pulled_pct": round(float(s.get("pulled_pct") or 0), 1),
        "remaining_m": round(float(s.get("remaining_m") or 0), 1),
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
    }


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
    joined = ds.load_joined(db)
    if joined is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    areas = _areas_file()
    as_of = as_of or date.today()
    thin = float(thin_pace if thin_pace is not None else plan.thin_pace)
    thick = float(thick_pace if thick_pace is not None else plan.thick_pace)
    h_st = float(h_per_stuetze if h_per_stuetze is not None else plan.h_per_stuetze)
    pull = int(pullers if pullers is not None else plan.pullers)
    max_room = int(max_per_room if max_per_room is not None else plan.max_per_room)
    hours = float(hours_per_week if hours_per_week is not None else plan.hours_per_week)
    summaries = summarize_all_areas(
        areas,
        joined,
        installed_by_area=plan.installed,
        thin_pace=thin,
        thick_pace=thick,
        h_per_stuetze=h_st,
        pullers=pull,
        hours_per_week=hours,
        max_per_room=max_room,
        as_of=as_of,
        priority_map={k: int(v) for k, v in (plan.priority or {}).items()},
    )
    totals = totals_from_summaries(summaries, pullers=pull, hours_per_week=hours, as_of=as_of)
    return summaries, totals, plan


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
    payload = [
        {
            "key": a.key,
            "name": a.name,
            "deck": a.deck,
            "area_ids": a.area_ids,
            "trays": a.trays,
            "penetrations": a.penetrations,
        }
        for a in areas
    ]
    (settings.appdata_path / "datasets" / _AREAS_PATH).write_text(json.dumps(payload), encoding="utf-8")
    return {"ok": True, "count": len(payload)}


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
    row = db.query(AreasSettings).first()
    payload = body.model_dump()
    if not row:
        row = AreasSettings(payload_json=json.dumps(payload))
        db.add(row)
    else:
        row.payload_json = json.dumps(payload)
    db.commit()
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
    return {
        "plan": plan.model_dump(),
        "summaries": [_sum_row(s) for s in summaries],
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
