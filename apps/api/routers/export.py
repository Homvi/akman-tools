from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import dataset as ds
from apps.api.services.cable_lookup import find_cables, lookup_export_frame, parse_cable_ids
from apps.api.services.filters import filter_cables
from src.pathways import cables_stopped_at

router = APIRouter(prefix="/export", tags=["export"])


def _frame(db, **filters):
    frame = ds.load_joined(db)
    if frame is None or frame.empty:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    frame = filter_cables(
        frame,
        devices=filters.get("devices"),
        pulled=filters.get("pulled"),
        thickness=filters.get("thickness"),
        categories=filters.get("categories"),
    )
    stop = filters.get("stop_stuetzen")
    if stop:
        nodes = [n.strip() for n in stop.split(",") if n.strip()]
        if nodes:
            frame = cables_stopped_at(frame, nodes)
    return frame


@router.get("/catra")
def export_catra(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
    devices: str | None = None,
    pulled: str | None = None,
    thickness: str | None = None,
    categories: str | None = None,
    stop_stuetzen: str | None = None,
):
    frame = _frame(
        db,
        devices=devices,
        pulled=pulled,
        thickness=thickness,
        categories=categories,
        stop_stuetzen=stop_stuetzen,
    )
    row = ds.current_dataset(db)
    header = json.loads(row.header_json) if row else []
    data = ds.export_catra(frame, header)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="catra.xlsx"'},
    )


@router.get("/kurzliste")
def export_kurzliste(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
    devices: str | None = None,
    pulled: str | None = None,
    thickness: str | None = None,
    categories: str | None = None,
    stop_stuetzen: str | None = None,
):
    frame = _frame(
        db,
        devices=devices,
        pulled=pulled,
        thickness=thickness,
        categories=categories,
        stop_stuetzen=stop_stuetzen,
    )
    data = ds.export_kurzliste(frame)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="kurzliste.xlsx"'},
    )


@router.get("/table")
def export_filtered_table(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
    devices: str | None = None,
    pulled: str | None = None,
    thickness: str | None = None,
    categories: str | None = None,
    filename: str = Query("export.xlsx"),
):
    frame = _frame(db, devices=devices, pulled=pulled, thickness=thickness, categories=categories)
    data = ds.export_table(frame)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


_DEVICE_COLS = ["Kabelnr", "Category", "Length_m", "Liste", "Geraet_A", "Geraet_E"]


@router.get("/device")
def export_device(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin", "worker")),
    device: str = Query(..., min_length=1, description="Gerät / cabinet name (matches A or E)"),
):
    name = device.strip()
    if not name:
        raise HTTPException(status_code=400, detail="device is required")
    frame = _frame(db, devices=name)
    cols = [c for c in _DEVICE_COLS if c in frame.columns]
    slim = frame[cols].copy() if cols else frame
    slug = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)[:80] or "device"
    data = ds.export_table(slim, sheet="Device")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="device_{slug}.xlsx"'},
    )


@router.get("/lookup")
def export_lookup(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin", "worker")),
    ids: str = Query(..., description="Semicolon-separated Kabelnr list"),
):
    id_list = parse_cable_ids(ids)
    if not id_list:
        raise HTTPException(status_code=400, detail="No cable IDs provided")
    frame = ds.load_joined(db)
    if frame is None or frame.empty:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    cables, _missing = find_cables(frame, id_list)
    if not cables:
        raise HTTPException(status_code=404, detail="No matching cables")
    data = ds.export_table(lookup_export_frame(cables), sheet="Lookup")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="kabel_lookup.xlsx"'},
    )
