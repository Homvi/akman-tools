"""Unified cable filter: Stützen/Bahn + device + status + thickness + category + stop."""

from __future__ import annotations

from typing import Any

import pandas as pd

from apps.api.services.filters import filter_cables
from src.pathways import cables_stopped_at
from src.stutzen_filter import (
    filter_by_nodes,
    filter_by_pull_statuses,
    parse_search_nodes,
    pull_status_counts,
    thickness_counts,
)

_ALL_STATUSES = frozenset({"not_started", "started", "fully_pulled"})


class CableFilterError(ValueError):
    """Invalid or empty filter request (HTTP 400)."""


def has_active_filter(
    *,
    nodes_text: str = "",
    devices: list[str] | None = None,
    statuses: list[str] | None = None,
    thickness: list[str] | None = None,
    categories: list[str] | None = None,
    stop_stuetzen: list[str] | None = None,
    unique_only: bool = True,
) -> bool:
    nodes = parse_search_nodes(nodes_text or "", unique_only=unique_only)
    if nodes:
        return True
    if any(str(d).strip() for d in (devices or [])):
        return True
    if any(str(t).strip() for t in (thickness or [])):
        return True
    if any(str(c).strip() for c in (categories or [])):
        return True
    if any(str(s).strip() for s in (stop_stuetzen or [])):
        return True
    status_keys = {str(s).strip() for s in (statuses or []) if str(s).strip()}
    # Narrowed pull-status set counts; all three (or empty = all) does not.
    if status_keys and status_keys != _ALL_STATUSES:
        return True
    return False


def apply_unified_filter(
    frame: pd.DataFrame,
    *,
    nodes_text: str = "",
    mode: str = "AND",
    unique_only: bool = True,
    statuses: list[str] | None = None,
    devices: list[str] | None = None,
    thickness: list[str] | None = None,
    categories: list[str] | None = None,
    stop_stuetzen: list[str] | None = None,
    require_filter: bool = True,
) -> dict[str, Any]:
    """
    Apply filters in order: nodes → devices/thick/cat → stop → pull status.

    Returns nodes, pre-status hits counts, and the final filtered frame.
    """
    if require_filter and not has_active_filter(
        nodes_text=nodes_text,
        devices=devices,
        statuses=statuses,
        thickness=thickness,
        categories=categories,
        stop_stuetzen=stop_stuetzen,
        unique_only=unique_only,
    ):
        raise CableFilterError("Select at least one filter (nodes, device, status, thickness, category, or stop)")

    nodes = parse_search_nodes(nodes_text or "", unique_only=unique_only)
    out = frame
    if nodes:
        out = filter_by_nodes(out, nodes, mode=mode or "AND")

    device_csv = ",".join(str(d).strip() for d in (devices or []) if str(d).strip()) or None
    thick_csv = ",".join(str(t).strip() for t in (thickness or []) if str(t).strip()) or None
    cat_csv = ",".join(str(c).strip() for c in (categories or []) if str(c).strip()) or None
    if device_csv or thick_csv or cat_csv:
        out = filter_cables(out, devices=device_csv, thickness=thick_csv, categories=cat_csv)

    stops = [str(s).strip() for s in (stop_stuetzen or []) if str(s).strip()]
    if stops:
        out = cables_stopped_at(out, stops)

    status_counts = pull_status_counts(out)
    thick_counts = thickness_counts(out)
    filtered = filter_by_pull_statuses(out, statuses)

    return {
        "nodes": nodes,
        "hits": out,
        "filtered": filtered,
        "status_counts": status_counts,
        "thickness_counts": thick_counts,
        "matched_total": int(sum(status_counts.values())),
    }
