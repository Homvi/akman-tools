from __future__ import annotations

import pandas as pd

from src.length_calc import (
    STATUS_NONE,
    _ordered_span,
    cable_pull_status,
    has_verlegt_date,
    latest_pull_ends,
    parse_route,
)
from src.stutzen_filter import cable_route

AT_DEVICE = "at_device"
STARTED = "started_not_at"
NOT_STARTED = "not_started"


def _text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "<na>", "none", "nat"} else text


def _same_device(value, device: str) -> bool:
    a = _text(value)
    b = _text(device)
    return bool(a and b and a == b)


def _geraet(row: pd.Series, side: str) -> str:
    if side == "A":
        return _text(row.get("Geraet_A") or row.get("A_Geraet"))
    return _text(row.get("Geraet_E") or row.get("E_Geraet"))


def _end_node(row: pd.Series, side: str, nodes: list[str]) -> str:
    if side == "A":
        node = _text(row.get("Knoten_A") or row.get("Point_A"))
        if not node and nodes:
            node = nodes[0]
        return node
    node = _text(row.get("Knoten_E") or row.get("Point_E"))
    if not node and nodes:
        node = nodes[-1]
    return node


def _node_index(nodes: list[str], needle: str) -> int | None:
    if not needle or not nodes:
        return None
    want = needle.casefold()
    for i, node in enumerate(nodes):
        if str(node).casefold() == want:
            return i
    return None


def device_sides(row: pd.Series, device: str) -> list[str]:
    sides: list[str] = []
    if _same_device(_geraet(row, "A"), device):
        sides.append("A")
    if _same_device(_geraet(row, "E"), device):
        sides.append("E")
    return sides


def side_pulled_to_device(row: pd.Series, side: str) -> bool:
    """True if the cable end at this device side is considered pulled."""
    if has_verlegt_date(row):
        return True
    if cable_pull_status(row) == STATUS_NONE:
        return False
    route = cable_route(row)
    nodes, _ = parse_route(route)
    pulled_start, pulled_end = latest_pull_ends(row)
    span = _ordered_span(nodes, pulled_start, pulled_end)
    if not span:
        return False
    end = _end_node(row, side, nodes)
    idx = _node_index(nodes, end)
    if idx is None:
        return False
    return span[0] <= idx <= span[1]


def cable_device_progress(row: pd.Series, device: str) -> str | None:
    """
    Classify cable relative to the selected device end(s):
    - at_device: pull reached the device end (or verlegt)
    - started_not_at: pull started elsewhere, device end not reached yet
    - not_started: no pull activity
    """
    sides = device_sides(row, device)
    if not sides:
        return None
    if all(side_pulled_to_device(row, side) for side in sides):
        return AT_DEVICE
    if cable_pull_status(row) != STATUS_NONE:
        return STARTED
    return NOT_STARTED


_PROGRESS_ALIASES = {
    "at": AT_DEVICE,
    "at_device": AT_DEVICE,
    "started": STARTED,
    "started_not_at": STARTED,
    "not_started": NOT_STARTED,
    "idle": NOT_STARTED,
}


def normalize_device_progress(value: str | None) -> str | None:
    if not value:
        return None
    key = str(value).strip().casefold()
    return _PROGRESS_ALIASES.get(key)


def filter_by_device_progress(df: pd.DataFrame, device: str, progress: str | None) -> pd.DataFrame:
    kind = normalize_device_progress(progress)
    if df is None or df.empty or not kind:
        return df
    name = _text(device)
    if not name:
        return df
    mask = df.apply(lambda row: cable_device_progress(row, name) == kind, axis=1)
    return df.loc[mask].copy()


def device_pull_stats(df: pd.DataFrame, device: str) -> dict:
    name = _text(device)
    empty = {
        "device_cables": 0,
        "device_at": 0,
        "device_started": 0,
        "device_not_started": 0,
        "device_side_pulled": 0,
        "device_side_pulled_pct": 0.0,
    }
    if df is None or df.empty or not name:
        return empty
    at = started = not_started = 0
    for _, row in df.iterrows():
        kind = cable_device_progress(row, name)
        if kind is None:
            continue
        if kind == AT_DEVICE:
            at += 1
        elif kind == STARTED:
            started += 1
        else:
            not_started += 1
    total = at + started + not_started
    pct = round(100.0 * at / total, 1) if total else 0.0
    return {
        "device_cables": total,
        "device_at": at,
        "device_started": started,
        "device_not_started": not_started,
        "device_side_pulled": at,
        "device_side_pulled_pct": pct,
    }
