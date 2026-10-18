from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import dataset as ds
from apps.api.services.filters import paginate
from src.stutzen_filter import filter_by_nodes, parse_search_nodes, search_nodes_stats

router = APIRouter(prefix="/stutzen", tags=["stutzen"])


class StutzenBody(BaseModel):
    nodes_text: str
    unique_only: bool = True
    mode: str = "AND"
    page: int = 1
    page_size: int = 100


@router.post("/filter")
def stutzen_filter(
    body: StutzenBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    frame = ds.load_joined(db)
    if frame is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    nodes = parse_search_nodes(body.nodes_text, unique_only=body.unique_only)
    stats = search_nodes_stats(body.nodes_text)
    hits = filter_by_nodes(frame, nodes, mode=body.mode)
    result = paginate(hits, page=body.page, page_size=body.page_size)
    result["nodes"] = nodes
    result["stats"] = stats
    return result
