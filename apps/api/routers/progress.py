from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import dataset as ds
from apps.api.services.jsonutil import records
from src.progress import build_pull_events, daily_progress, progress_stats, weekly_progress

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/daily")
def progress_daily(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
    kinds: str | None = Query(None, description="Comma-separated event kinds"),
):
    frame = ds.load_joined(db)
    if frame is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    events = build_pull_events(frame)
    kind_list = [k.strip() for k in kinds.split(",")] if kinds else None
    daily = daily_progress(events, kind_list)
    weekly = weekly_progress(daily)
    stats = progress_stats(events, daily)
    return {
        "daily": records(daily),
        "weekly": records(weekly),
        "stats": stats,
    }
