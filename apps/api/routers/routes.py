from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import dataset as ds
from apps.api.services.filters import filter_cables
from src.pathways import route_groups

router = APIRouter(prefix="/routes", tags=["routes"])


@router.get("/groups")
def get_route_groups(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
    similarity: float = Query(0.9, ge=0.5, le=1.0),
    min_size: int = Query(2, ge=2),
    devices: str | None = None,
    pulled: str | None = None,
    thickness: str | None = None,
    categories: str | None = None,
):
    frame = ds.load_joined(db)
    if frame is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    frame = filter_cables(frame, devices=devices, pulled=pulled, thickness=thickness, categories=categories)
    groups = route_groups(frame, similarity=similarity, min_size=min_size)
    if groups is None or (hasattr(groups, "empty") and groups.empty):
        return {"groups": []}
    if isinstance(groups, list):
        return {"groups": groups}
    return {"groups": groups.where(groups.notna(), None).to_dict(orient="records")}
