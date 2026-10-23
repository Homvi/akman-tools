from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import dataset as ds
from apps.api.services.device_stats import filter_by_device_progress
from apps.api.services.filters import filter_cables
from apps.api.services.priority_devices import (
    PRIORITY_DEVICE_NAMES,
    priority_devices_summary,
    priority_export_frame,
)
from src.pull_cards_pdf import build_pull_cards_pdf
from src.stutzen_filter import (
    DEFAULT_EXPORT_COLUMNS,
    export_column_catalog,
    select_export_columns,
)

router = APIRouter(prefix="/devices", tags=["devices"])


class PriorityExportBody(BaseModel):
    devices: list[str] = Field(default_factory=lambda: list(PRIORITY_DEVICE_NAMES))
    statuses: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=lambda: list(DEFAULT_EXPORT_COLUMNS))


class DeviceExportBody(BaseModel):
    device: str
    device_progress: str | None = None
    columns: list[str] = Field(default_factory=lambda: list(DEFAULT_EXPORT_COLUMNS))


class DevicePullCardsBody(BaseModel):
    device: str
    device_progress: str | None = None
    filter_note: str = ""
    lang: str = "en"


class PriorityPullCardsBody(BaseModel):
    devices: list[str] = Field(default_factory=lambda: list(PRIORITY_DEVICE_NAMES))
    statuses: list[str] = Field(default_factory=list)
    filter_note: str = ""
    lang: str = "en"


def _device_frame(db: Session, device: str, device_progress: str | None = None):
    name = (device or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="device is required")
    frame = ds.load_joined(db)
    if frame is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    hits = filter_cables(frame, devices=name)
    if device_progress:
        hits = filter_by_device_progress(hits, name, device_progress)
    return name, hits


@router.get("/priority")
def list_priority_devices(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    frame = ds.load_joined(db)
    if frame is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    return {"devices": priority_devices_summary(frame)}


@router.get("/priority/export-columns")
def priority_export_columns(_: User = Depends(require_roles("planner", "admin"))):
    return {"columns": export_column_catalog(), "defaults": list(DEFAULT_EXPORT_COLUMNS)}


@router.post("/priority/export")
def export_priority_devices(
    body: PriorityExportBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    frame = ds.load_joined(db)
    if frame is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    devices = body.devices or list(PRIORITY_DEVICE_NAMES)
    filtered = priority_export_frame(frame, devices=devices, statuses=body.statuses)
    if filtered.empty:
        raise HTTPException(status_code=404, detail="No matching cables")
    slim = select_export_columns(filtered, body.columns)
    data = ds.export_table(slim, sheet="PriorityDevices")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="priority_devices.xlsx"'},
    )


@router.post("/priority/pull-cards")
def priority_pull_cards(
    body: PriorityPullCardsBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    frame = ds.load_joined(db)
    if frame is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    devices = body.devices or list(PRIORITY_DEVICE_NAMES)
    filtered = priority_export_frame(frame, devices=devices, statuses=body.statuses)
    if filtered.empty:
        raise HTTPException(status_code=404, detail="No matching cables")
    lang = (body.lang or "en").strip().lower()
    if lang not in {"en", "hu", "de"}:
        lang = "en"
    note = (body.filter_note or "").strip() or f"Priority devices · {len(devices)} devices"
    data = build_pull_cards_pdf(filtered, filter_note=note, lang=lang, highlight_nodes=None)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="priority_pull_cards.pdf"'},
    )


@router.post("/export")
def export_device_columns(
    body: DeviceExportBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    name, hits = _device_frame(db, body.device, body.device_progress)
    if hits.empty:
        raise HTTPException(status_code=404, detail="No matching cables")
    slim = select_export_columns(hits, body.columns)
    slug = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)[:80] or "device"
    data = ds.export_table(slim, sheet="Device")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="device_{slug}.xlsx"'},
    )


@router.post("/pull-cards")
def device_pull_cards(
    body: DevicePullCardsBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    name, hits = _device_frame(db, body.device, body.device_progress)
    if hits.empty:
        raise HTTPException(status_code=404, detail="No matching cables")
    lang = (body.lang or "en").strip().lower()
    if lang not in {"en", "hu", "de"}:
        lang = "en"
    note = (body.filter_note or "").strip() or name
    data = build_pull_cards_pdf(hits, filter_note=note, lang=lang, highlight_nodes=None)
    slug = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)[:60] or "device"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="device_{slug}_pull_cards.pdf"'},
    )
