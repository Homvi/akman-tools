from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import cable_filter as filt
from apps.api.services import dataset as ds
from apps.api.services.filters import paginate
from src.pull_cards_pdf import build_pull_cards_pdf
from src.stutzen_filter import (
    DEFAULT_EXPORT_COLUMNS,
    export_column_catalog,
    select_export_columns,
)

router = APIRouter(prefix="/filter", tags=["filter"])


class FilterBody(BaseModel):
    nodes_text: str = ""
    unique_only: bool = True
    mode: str = "AND"
    statuses: list[str] = Field(default_factory=list)
    devices: list[str] = Field(default_factory=list)
    thickness: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    stop_stuetzen: list[str] = Field(default_factory=list)
    page: int = 1
    page_size: int = 100


class FilterExportBody(BaseModel):
    nodes_text: str = ""
    unique_only: bool = True
    mode: str = "AND"
    statuses: list[str] = Field(default_factory=list)
    devices: list[str] = Field(default_factory=list)
    thickness: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    stop_stuetzen: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=lambda: list(DEFAULT_EXPORT_COLUMNS))


class FilterPullCardsBody(BaseModel):
    nodes_text: str = ""
    unique_only: bool = True
    mode: str = "AND"
    statuses: list[str] = Field(default_factory=list)
    devices: list[str] = Field(default_factory=list)
    thickness: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    stop_stuetzen: list[str] = Field(default_factory=list)
    filter_note: str = ""
    lang: str = "en"


def _run(db: Session, body: FilterBody | FilterExportBody | FilterPullCardsBody):
    frame = ds.load_joined(db)
    if frame is None:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    try:
        return filt.apply_unified_filter(
            frame,
            nodes_text=body.nodes_text,
            mode=body.mode,
            unique_only=body.unique_only,
            statuses=body.statuses,
            devices=body.devices,
            thickness=body.thickness,
            categories=body.categories,
            stop_stuetzen=body.stop_stuetzen,
        )
    except filt.CableFilterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.get("/export-columns")
def filter_export_columns(_: User = Depends(require_roles("planner", "admin"))):
    return {"columns": export_column_catalog(), "defaults": list(DEFAULT_EXPORT_COLUMNS)}


@router.post("/query")
def filter_query(
    body: FilterBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    result = _run(db, body)
    page = paginate(result["filtered"], page=body.page, page_size=body.page_size)
    page["nodes"] = result["nodes"]
    page["status_counts"] = result["status_counts"]
    page["thickness_counts"] = result["thickness_counts"]
    page["matched_total"] = result["matched_total"]
    return page


@router.post("/export")
def filter_export(
    body: FilterExportBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    result = _run(db, body)
    filtered = result["filtered"]
    if filtered.empty:
        raise HTTPException(status_code=404, detail="No matching cables")
    slim = select_export_columns(filtered, body.columns)
    data = ds.export_table(slim, sheet="Kurzliste")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="kurzliste.xlsx"'},
    )


@router.post("/pull-cards")
def filter_pull_cards(
    body: FilterPullCardsBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    result = _run(db, body)
    filtered = result["filtered"]
    if filtered.empty:
        raise HTTPException(status_code=404, detail="No matching cables")
    nodes = result["nodes"]
    note = (body.filter_note or "").strip()
    if not note:
        parts = []
        if nodes:
            parts.append(f"{', '.join(nodes)} ({body.mode})")
        if body.devices:
            parts.append("devices: " + ", ".join(body.devices[:8]))
        note = " · ".join(parts) or "filter"
    lang = (body.lang or "en").strip().lower()
    if lang not in {"en", "hu", "de"}:
        lang = "en"
    data = build_pull_cards_pdf(
        filtered,
        filter_note=note,
        lang=lang,
        highlight_nodes=nodes or None,
    )
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="filter_pull_cards.pdf"'},
    )
