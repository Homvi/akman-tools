from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import dataset as ds
from apps.api.services.filters import paginate
from src.pull_cards_pdf import build_pull_cards_pdf
from src.stutzen_filter import (
    DEFAULT_EXPORT_COLUMNS,
    export_column_catalog,
    filter_by_nodes,
    filter_by_pull_statuses,
    parse_search_nodes,
    pull_status_counts,
    search_nodes_stats,
    select_export_columns,
    stutzen_filename,
    thickness_counts,
)

router = APIRouter(prefix="/stutzen", tags=["stutzen"])


class StutzenBody(BaseModel):
    nodes_text: str
    unique_only: bool = True
    mode: str = "AND"
    statuses: list[str] = Field(default_factory=list)
    page: int = 1
    page_size: int = 100


class StutzenExportBody(BaseModel):
    nodes_text: str
    unique_only: bool = True
    mode: str = "AND"
    statuses: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=lambda: list(DEFAULT_EXPORT_COLUMNS))


class StutzenPullCardsBody(BaseModel):
    nodes_text: str
    unique_only: bool = True
    mode: str = "AND"
    statuses: list[str] = Field(default_factory=list)
    filter_note: str = ""
    lang: str = "en"


def _filtered_hits(db: Session, body: StutzenBody | StutzenExportBody | StutzenPullCardsBody):
    frame = ds.load_joined(db)
    if frame is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    nodes = parse_search_nodes(body.nodes_text, unique_only=body.unique_only)
    if not nodes:
        raise HTTPException(status_code=400, detail="Enter at least one Stütze / Bahn number")
    hits = filter_by_nodes(frame, nodes, mode=body.mode)
    status_counts = pull_status_counts(hits)
    thick_counts = thickness_counts(hits)
    filtered = filter_by_pull_statuses(hits, body.statuses)
    return nodes, hits, filtered, status_counts, thick_counts


@router.get("/export-columns")
def stutzen_export_columns(_: User = Depends(require_roles("planner", "admin"))):
    return {"columns": export_column_catalog(), "defaults": list(DEFAULT_EXPORT_COLUMNS)}


@router.post("/filter")
def stutzen_filter(
    body: StutzenBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    nodes, _hits, filtered, status_counts, thick_counts = _filtered_hits(db, body)
    stats = search_nodes_stats(body.nodes_text)
    result = paginate(filtered, page=body.page, page_size=body.page_size)
    result["nodes"] = nodes
    result["stats"] = stats
    result["status_counts"] = status_counts
    result["thickness_counts"] = thick_counts
    result["matched_total"] = int(sum(status_counts.values()))
    return result


@router.post("/export")
def stutzen_export(
    body: StutzenExportBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    nodes, _hits, filtered, _status_counts, _thick_counts = _filtered_hits(db, body)
    if filtered.empty:
        raise HTTPException(status_code=404, detail="No matching cables")
    slim = select_export_columns(filtered, body.columns)
    data = ds.export_table(slim, sheet="Stutzen")
    fname = stutzen_filename(nodes)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.post("/pull-cards")
def stutzen_pull_cards(
    body: StutzenPullCardsBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    nodes, _hits, filtered, _status_counts, _thick_counts = _filtered_hits(db, body)
    if filtered.empty:
        raise HTTPException(status_code=404, detail="No matching cables")
    note = (body.filter_note or "").strip()
    if not note:
        note = f"{', '.join(nodes)} ({body.mode})"
    lang = (body.lang or "en").strip().lower()
    if lang not in {"en", "hu", "de"}:
        lang = "en"
    data = build_pull_cards_pdf(
        filtered,
        filter_note=note,
        lang=lang,
        highlight_nodes=nodes,
    )
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="stutzen_pull_cards.pdf"'},
    )
