from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import dataset as ds
from apps.api.services.filters import paginate
from apps.api.services.jsonutil import records
from src.analysis import aggregate_stops, stopped_by_location

router = APIRouter(prefix="/stopped", tags=["stopped"])


@router.get("/summary")
def stopped_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    frame = ds.load_joined(db)
    if frame is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    detail = stopped_by_location(frame)
    summary = aggregate_stops(detail)
    return {
        "summary": records(summary),
        "detail": records(detail),
    }


@router.get("/at/{location}")
def stopped_at(
    location: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
    page: int = 1,
    page_size: int = 100,
):
    frame = ds.load_joined(db)
    if frame is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    detail = stopped_by_location(frame)
    part = detail[detail["Stop_location"].astype(str) == location] if not detail.empty else detail
    return paginate(part, page=page, page_size=page_size)
