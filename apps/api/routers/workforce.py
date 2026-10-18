from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import dataset as ds
from apps.api.services.jsonutil import records
from src.progress import build_pull_events, daily_progress
from src.workforce import (
    daily_headcount,
    daily_hours,
    headcount_growth,
    meters_per_hour,
    meters_per_person,
    parse_workforce_excel,
)

router = APIRouter(prefix="/workforce", tags=["workforce"])

_WF_PATH = "workforce.parquet"


@router.post("/upload")
async def upload_workforce(
    file: UploadFile = File(...),
    year: int = 2026,
    _: User = Depends(require_roles("planner", "admin")),
):
    path = settings.appdata_path / "uploads" / "workforce.xlsx"
    path.write_bytes(await file.read())
    try:
        frame = parse_workforce_excel(path, year=year)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    out = settings.appdata_path / "datasets" / _WF_PATH
    frame.to_parquet(out, index=False)
    return {"ok": True, "rows": len(frame), "people": int(frame["Name"].nunique()) if "Name" in frame.columns else 0}


@router.get("/series")
def workforce_series(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    path = settings.appdata_path / "datasets" / _WF_PATH
    if not path.exists():
        raise HTTPException(status_code=404, detail="No workforce data")
    import pandas as pd

    wf = pd.read_parquet(path)
    daily_hc = daily_headcount(wf)
    hours = daily_hours(wf)
    growth = headcount_growth(daily_hc)
    meters_daily = None
    joined = ds.load_joined(db)
    if joined is not None and not joined.empty:
        events = build_pull_events(joined)
        meters_daily = daily_progress(events)
    m_person = meters_per_person(daily_hc, meters_daily) if meters_daily is not None else None
    m_hour = meters_per_hour(hours, meters_daily) if meters_daily is not None else None
    return {
        "headcount": records(daily_hc),
        "hours": records(hours),
        "growth": growth,
        "m_per_person": records(m_person) if m_person is not None else [],
        "m_per_hour": records(m_hour) if m_hour is not None else [],
    }
