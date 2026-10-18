from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import dataset as ds
from apps.api.services.cable_lookup import (
    cable_detail,
    find_cable,
    find_cables,
    parse_cable_ids,
    search_cable_ids,
)
from apps.api.services.device_stats import device_pull_stats, filter_by_device_progress
from apps.api.services.filters import filter_cables, filter_options, paginate
from apps.api.services.jsonutil import safe_float
from src.analysis import PULL_PARTIAL, PULL_YES, cable_numbers
from src.pathways import cables_stopped_at

router = APIRouter(tags=["cables"])


def _joined(db: Session):
    frame = ds.load_joined(db)
    if frame is None or frame.empty:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    return frame


@router.get("/filters/options")
def get_filter_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin", "worker")),
):
    return filter_options(_joined(db))


@router.get("/cables/lookup")
def lookup_cables(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin", "worker")),
    ids: str = Query(..., description="Comma-separated Kabelnr list"),
):
    id_list = parse_cable_ids(ids)
    if not id_list:
        raise HTTPException(status_code=400, detail="No cable IDs provided")
    cables, missing = find_cables(_joined(db), id_list)
    return {"cables": cables, "missing": missing, "ids": id_list}


@router.get("/cables/search")
def search_cables(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin", "worker")),
    q: str = Query("", min_length=0),
    limit: int = Query(40, ge=1, le=100),
):
    """Live typeahead for Kabelnr (calculator / quick pick)."""
    query = (q or "").strip()
    if len(query) < 1:
        return {"ids": [], "q": query}
    return {"ids": search_cable_ids(_joined(db), query, limit=limit), "q": query}


@router.get("/cables/by-id/{kabelnr}")
def get_cable_by_id(
    kabelnr: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin", "worker")),
):
    row = find_cable(_joined(db), kabelnr)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Cable {kabelnr} not found")
    return cable_detail(row)


@router.get("/cables")
def list_cables(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin", "worker")),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    devices: str | None = None,
    device_progress: str | None = None,
    pulled: str | None = None,
    thickness: str | None = None,
    categories: str | None = None,
    stop_stuetzen: str | None = None,
):
    frame = filter_cables(
        _joined(db),
        devices=devices,
        pulled=pulled,
        thickness=thickness,
        categories=categories,
    )
    if stop_stuetzen:
        nodes = [n.strip() for n in stop_stuetzen.split(",") if n.strip()]
        if nodes:
            frame = cables_stopped_at(frame, nodes)
    device_name = devices.split(",")[0].strip() if devices and devices.strip() else ""
    device_metrics = device_pull_stats(frame, device_name) if device_name else {}
    if device_name and device_progress:
        frame = filter_by_device_progress(frame, device_name, device_progress)
    result = paginate(frame, page=page, page_size=page_size)
    length_m = 0.0
    if "Length_m" in frame.columns:
        length_m = safe_float(frame["Length_m"].fillna(0).sum())
    pulled = cable_numbers(frame[frame["Pull_status"] == PULL_YES]) if "Pull_status" in frame.columns else []
    partial = cable_numbers(frame[frame["Pull_status"] == PULL_PARTIAL]) if "Pull_status" in frame.columns else []
    thick_count = 0
    thin_count = 0
    if "Thickness" in frame.columns:
        thick_count = int((frame["Thickness"] == "Thick").sum())
        thin_count = int((frame["Thickness"] == "Thin").sum())
    result["metrics"] = {
        "count": len(frame),
        "pulled": [x for x in pulled[:500] if x is not None and str(x) != "nan"],
        "partial": [x for x in partial[:500] if x is not None and str(x) != "nan"],
        "length_m": length_m,
        "pulled_count": int((frame["Pull_status"] == PULL_YES).sum()) if "Pull_status" in frame.columns else 0,
        "partial_count": int((frame["Pull_status"] == PULL_PARTIAL).sum()) if "Pull_status" in frame.columns else 0,
        "thick_count": thick_count,
        "thin_count": thin_count,
        **device_metrics,
    }
    return result
