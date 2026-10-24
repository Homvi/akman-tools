from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import Dataset, User
from apps.api.services import dataset as ds
from apps.api.services.areas_cache import clear_areas_cache

router = APIRouter(prefix="/dataset", tags=["dataset"])


@router.get("")
def get_dataset(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin", "worker")),
):
    return ds.dataset_payload(db)


@router.get("/status")
def get_dataset_status(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin", "worker")),
):
    """Fast AuthGate check — no parquet / progress date computation."""
    return ds.dataset_status(db)


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin", "worker")),
):
    row = ds.current_dataset(db)
    if not row:
        return {
            "loaded": False,
            **ds.progress_as_of(None),
            **ds.length_summary(None),
            "wired_not_verlegt": [],
            "anschluss_without_verlegt": [],
        }
    frame = ds.load_joined(db)
    open_anschluss = ds.anschluss_without_verlegt(frame)
    return {
        "loaded": True,
        "status_name": row.status_name,
        "catra_name": row.catra_name,
        **ds.progress_as_of(frame),
        **ds.length_summary(frame),
        "wired_not_verlegt": ds.wired_not_verlegt(frame),
        "anschluss_without_verlegt": open_anschluss,
    }


@router.post("/upload")
async def upload_dataset(
    status_file: UploadFile = File(...),
    catra_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    try:
        row = ds.ingest_uploads(db, status_file=status_file, catra_file=catra_file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse files: {exc}") from exc
    clear_areas_cache()
    payload = ds.dataset_payload(db, row)
    return payload


@router.delete("")
def clear_dataset(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    db.query(Dataset).delete()
    db.commit()
    clear_areas_cache()
    return {"ok": True}
