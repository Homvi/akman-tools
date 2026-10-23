from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import dataset as ds
from apps.api.services import live_progressliste as live_pl
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


def _filtered(db: Session, max_remaining_m: float, *, exclude_live_verlegt: bool = False):
    frame = ds.load_joined(db)
    if frame is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    capped = _clamp_max_remaining(max_remaining_m)
    part = near_complete_cables(frame, max_remaining_m=capped)
    part, missing = live_pl.exclude_live_verlegt(part, enabled=exclude_live_verlegt)
    return frame, part, capped, missing


@router.get("/live-progressliste")
def live_progressliste_status(_: User = Depends(require_roles("planner", "admin"))):
    return live_pl.status()


@router.post("/live-progressliste")
async def upload_live_progressliste(
    file: UploadFile = File(...),
    _: User = Depends(require_roles("planner", "admin")),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        meta = live_pl.save_live_progressliste(data, file_name=file.filename or "")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return meta


@router.get("")
def list_near_complete(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
    max_remaining_m: float = Query(15.0, ge=_MAX_REMAINING_MIN, le=_MAX_REMAINING_MAX),
    exclude_live_verlegt: bool = Query(False),
):
    frame, part, capped, missing = _filtered(db, max_remaining_m, exclude_live_verlegt=exclude_live_verlegt)
    rem = part["Remaining_m"] if not part.empty and "Remaining_m" in part.columns else None
    remaining_total = float(rem.sum()) if rem is not None else 0.0
    length_col = part["Length_m"] if not part.empty and "Length_m" in part.columns else None
    fully_pulled_gain = float(length_col.fillna(0).sum()) if length_col is not None else 0.0
    live = live_pl.status()
    # With live filter on: project fully-pulled total as in the éles Progressliste
    # (current live verlegt meters + Length_m of remaining near-complete rows).
    use_live_metric = bool(exclude_live_verlegt and live.get("loaded") and not missing)
    if use_live_metric:
        fully_pulled_now = live_pl.live_fully_pulled_m(frame)
        metric_basis = "live"
    else:
        fully_pulled_now = float(ds.length_summary(frame).get("fully_pulled_m") or 0.0)
        metric_basis = "dataset"
    cols = [c for c in _TABLE_COLS if c in part.columns]
    slim = part[cols] if cols else part
    return {
        "rows": records(slim),
        "total": int(len(part)),
        "remaining_total_m": round(remaining_total, 1),
        "fully_pulled_m": round(fully_pulled_now, 1),
        "fully_pulled_gain_m": round(fully_pulled_gain, 1),
        "fully_pulled_after_m": round(fully_pulled_now + fully_pulled_gain, 1),
        "metric_basis": metric_basis,
        "max_remaining_m": capped,
        "exclude_live_verlegt": bool(exclude_live_verlegt),
        "live_progressliste_missing": bool(exclude_live_verlegt and missing),
        "live_progressliste": live,
    }


@router.get("/export")
def export_near_complete(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
    max_remaining_m: float = Query(15.0, ge=_MAX_REMAINING_MIN, le=_MAX_REMAINING_MAX),
    exclude_live_verlegt: bool = Query(False),
):
    _frame, part, capped, _missing = _filtered(db, max_remaining_m, exclude_live_verlegt=exclude_live_verlegt)
    cols = [c for c in _TABLE_COLS if c in part.columns]
    slim = part[cols] if cols else part
    data = to_xlsx_bytes(slim, sheet_name="NearComplete")
    slug = str(int(capped)) if capped == int(capped) else str(capped).replace(".", "_")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="near_complete_{slug}m.xlsx"'},
    )
