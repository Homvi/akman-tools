from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import dataset as ds
from apps.api.services.jsonutil import records
from src.analysis import near_complete_cables
from src.export import to_xlsx_bytes

router = APIRouter(prefix="/near-complete", tags=["near-complete"])

_TABLE_COLS = [
    "Kabelnr",
    "Remaining_m",
    "Length_m",
    "Total_teilgezogene_meter",
    "Category",
    "Liste",
    "Thickness",
    "Geraet_A",
    "Geraet_E",
    "Pull_status",
]

_MAX_REMAINING_MIN = 1.0
_MAX_REMAINING_MAX = 100.0


def _clamp_max_remaining(value: float) -> float:
    return max(_MAX_REMAINING_MIN, min(_MAX_REMAINING_MAX, float(value)))


def _filtered(db: Session, max_remaining_m: float):
    frame = ds.load_joined(db)
    if frame is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    capped = _clamp_max_remaining(max_remaining_m)
    return near_complete_cables(frame, max_remaining_m=capped), capped


@router.get("")
def list_near_complete(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
    max_remaining_m: float = Query(15.0, ge=_MAX_REMAINING_MIN, le=_MAX_REMAINING_MAX),
):
    part, capped = _filtered(db, max_remaining_m)
    rem = part["Remaining_m"] if not part.empty and "Remaining_m" in part.columns else None
    remaining_total = float(rem.sum()) if rem is not None else 0.0
    cols = [c for c in _TABLE_COLS if c in part.columns]
    slim = part[cols] if cols else part
    return {
        "rows": records(slim),
        "total": int(len(part)),
        "remaining_total_m": round(remaining_total, 1),
        "max_remaining_m": capped,
    }


@router.get("/export")
def export_near_complete(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
    max_remaining_m: float = Query(15.0, ge=_MAX_REMAINING_MIN, le=_MAX_REMAINING_MAX),
):
    part, capped = _filtered(db, max_remaining_m)
    cols = [c for c in _TABLE_COLS if c in part.columns]
    slim = part[cols] if cols else part
    data = to_xlsx_bytes(slim, sheet_name="NearComplete")
    slug = str(int(capped)) if capped == int(capped) else str(capped).replace(".", "_")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="near_complete_{slug}m.xlsx"'},
    )
