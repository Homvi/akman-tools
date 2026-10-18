from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import dataset as ds
from apps.api.services.filters import paginate
from src.ids import cable_id_list_stats, select_cables_by_ids

router = APIRouter(prefix="/ids", tags=["ids"])


class IdBody(BaseModel):
    text: str
    dedupe: bool = True
    page: int = 1
    page_size: int = 100


@router.post("/lookup")
def lookup_ids(
    body: IdBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    frame = ds.load_joined(db)
    if frame is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    stats = cable_id_list_stats(body.text)
    matched, found, missing = select_cables_by_ids(frame, body.text, dedupe=body.dedupe)
    result = paginate(matched, page=body.page, page_size=body.page_size)
    result["stats"] = stats
    result["found"] = found
    result["missing"] = missing
    return result
