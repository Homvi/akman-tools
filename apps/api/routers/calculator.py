from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.api.deps import require_roles
from apps.api.models import User
from src.length_calc import (
    analyze_overlap,
    calculate_pulled_length,
    highlight_route_layers,
    parse_route,
)

router = APIRouter(prefix="/calc", tags=["calculator"])


class CalcBody(BaseModel):
    route: str
    start: str
    end: str
    node_a: str = ""
    node_e: str = ""
    allowance_a: float = 0
    allowance_e: float = 0


class PreviewBody(BaseModel):
    route: str
    pulled_start: str = ""
    pulled_end: str = ""
    start: str = ""
    end: str = ""


@router.post("/length")
def calc_length(body: CalcBody, _: User = Depends(require_roles("planner", "admin", "worker"))):
    nodes, distances = parse_route(body.route)
    result = calculate_pulled_length(
        body.route,
        body.node_a,
        body.allowance_a,
        body.node_e,
        body.allowance_e,
        body.start,
        body.end,
    )
    return {
        "nodes": nodes,
        "distances": distances,
        "result": asdict(result),
    }


@router.post("/preview")
def calc_preview(body: PreviewBody, _: User = Depends(require_roles("planner", "admin", "worker"))):
    """Highlight already-pulled (orange) vs newly selected (blue) segments; flag overlap."""
    route_html = highlight_route_layers(
        body.route,
        pulled_start=body.pulled_start,
        pulled_end=body.pulled_end,
        selected_start=body.start,
        selected_end=body.end,
    )
    advice = analyze_overlap(
        body.route,
        body.pulled_start,
        body.pulled_end,
        body.start,
        body.end,
    )
    return {
        "route_html": route_html,
        "overlap": asdict(advice),
    }
