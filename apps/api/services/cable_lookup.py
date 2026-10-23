from __future__ import annotations

import pandas as pd

from src.analysis import assign_pull_status
from src.dates import parse_flexible_date
from src.length_calc import (
    STATUS_COMPLETE,
    STATUS_NONE,
    STATUS_PARTIAL,
    calculate_pulled_length,
    cable_pull_status,
    highlight_pulled_segment,
    latest_pull_ends,
    parse_route,
)
from src.ids import SPLIT_CABLE_IDS, join_key, normalize_kabel_id
from src.stutzen_filter import cable_route


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


def _num(value) -> float | None:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        text = _text(value).replace(",", ".")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None


def _fmt_date(value) -> str | None:
    ts = parse_flexible_date(value)
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).strftime("%d.%m.%Y")


def parse_cable_ids(raw: str | list[str] | None) -> list[str]:
    """Split pasted IDs on semicolon / newlines only — never on commas or spaces.

    Kabelnr values like ``2114,1`` / ``5077, 2`` (or ``2114.1``) stay one token.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        parts = raw
    else:
        parts = SPLIT_CABLE_IDS.split(str(raw))
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        token = str(part or "").strip().strip(",")
        if not token:
            continue
        id_ = normalize_kabel_id(token) or token
        if not id_ or id_ in seen:
            continue
        seen.add(id_)
        out.append(id_)
    return out


def find_cable(df: pd.DataFrame, kabelnr: str) -> pd.Series | None:
    if df is None or df.empty or "Kabelnr" not in df.columns:
        return None
    needle = str(kabelnr or "").strip()
    if not needle:
        return None
    frame = assign_pull_status(df)
    keys = frame["Kabelnr"].astype(str).str.strip()
    hits = frame[keys == needle]
    if hits.empty:
        needle_norm = normalize_kabel_id(needle) or needle
        hits = frame[keys == needle_norm]
    if hits.empty:
        needle_jk = join_key(needle)
        if needle_jk:
            if "join_key" in frame.columns:
                jk = frame["join_key"].astype(str)
            else:
                jk = keys.map(join_key)
            hits = frame[jk == needle_jk]
    if hits.empty:
        hits = frame[keys.str.lstrip("0") == needle.lstrip("0")]
    if hits.empty:
        return None
    return hits.iloc[0]


def search_cable_ids(df: pd.DataFrame, query: str, *, limit: int = 40) -> list[str]:
    """Typeahead: Kabelnr containing query (case-insensitive), shortest first."""
    if df is None or df.empty or "Kabelnr" not in df.columns:
        return []
    q = str(query or "").strip().lower()
    if not q:
        return []
    ids = (
        df["Kabelnr"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda s: s.str.len().gt(0)]
        .unique()
        .tolist()
    )
    q_stripped = q.lstrip("0") or q
    scored: list[tuple[int, int, str]] = []
    for kabelnr in ids:
        low = kabelnr.lower()
        if q not in low and q_stripped not in low.lstrip("0"):
            continue
        if low.startswith(q) or low.lstrip("0").startswith(q_stripped):
            rank = 0
        elif q in low:
            rank = 1
        else:
            rank = 2
        scored.append((rank, len(kabelnr), kabelnr))
    scored.sort()
    return [item[2] for item in scored[: max(1, min(int(limit or 40), 100))]]


def find_cables(df: pd.DataFrame, ids: list[str]) -> tuple[list[dict], list[str]]:
    found: list[dict] = []
    missing: list[str] = []
    for kabelnr in ids:
        row = find_cable(df, kabelnr)
        if row is None:
            missing.append(kabelnr)
        else:
            found.append(cable_detail(row))
    return found, missing


def _latest_stop_date(row: pd.Series) -> str | None:
    dates: list[pd.Timestamp] = []
    for col in ("Gestoppt_1", "Gestoppt_2", "Gestoppt_3"):
        ts = parse_flexible_date(row.get(col))
        if not pd.isna(ts):
            dates.append(pd.Timestamp(ts))
    if not dates:
        return None
    return max(dates).strftime("%d.%m.%Y")


_ROUTE_MISSING_MSG = (
    "Nincs nyomvonal (Pfad) a Gesamtliste-ben — a behúzott szakasz nem jeleníthető meg."
)


def cable_detail(row: pd.Series) -> dict:
    status = cable_pull_status(row)
    route = cable_route(row)
    nodes, distances = parse_route(route)
    # Drop NaN-like tokens if a bad path slipped through.
    nodes = [n for n in nodes if _text(n)]
    distances = distances[: max(0, len(nodes) - 1)] if nodes else []
    pulled_start, pulled_end = latest_pull_ends(row)
    verlegt_date = _fmt_date(row.get("verlegt"))
    stop_date = _latest_stop_date(row)
    route_missing = status in {STATUS_COMPLETE, STATUS_PARTIAL} and not nodes
    route_warning = _ROUTE_MISSING_MSG if route_missing else ""

    if status == STATUS_COMPLETE:
        status_message = f"Behúzva: {verlegt_date}" if verlegt_date else "Teljesen behúzva"
        if nodes:
            route_html = highlight_pulled_segment(route, nodes[0], nodes[-1])
            pulled_start = nodes[0]
            pulled_end = nodes[-1]
        else:
            route_html = ""
            pulled_start = ""
            pulled_end = ""
            status_message = f"{status_message} · {route_warning}"
    elif status == STATUS_PARTIAL and (pulled_start or pulled_end):
        span = f"{pulled_start or '—'} → {pulled_end or '—'}"
        if stop_date:
            status_message = f"Részlegesen behúzva {stop_date}-án/én · {span}"
        else:
            status_message = f"Részlegesen behúzva · {span}"
        if nodes:
            route_html = highlight_pulled_segment(route, pulled_start, pulled_end)
        else:
            route_html = ""
            status_message = f"{status_message} · {route_warning}"
    elif status == STATUS_PARTIAL:
        route_html = ""
        status_message = "Részlegesen behúzva"
        if route_missing:
            status_message = f"{status_message} · {route_warning}"
    else:
        route_html = highlight_pulled_segment(route, "", "") if route else ""
        status_message = "Nincs behúzás"

    cable_type = _text(row.get("Artikel") or row.get("Kabeltyp"))
    adern = _text(row.get("Typ") or row.get("Kabeladern"))
    geraet_a = _text(row.get("Geraet_A") or row.get("A_Geraet"))
    geraet_e = _text(row.get("Geraet_E") or row.get("E_Geraet"))
    ort_a = _text(row.get("Ort_A") or row.get("A_Ort"))
    ort_e = _text(row.get("Ort_E") or row.get("E_Ort"))
    aln_a = _text(row.get("Aln_A"))
    aln_e = _text(row.get("Aln_E"))
    node_a = _text(row.get("Knoten_A")) or _text(row.get("Point_A")) or (nodes[0] if nodes else "")
    node_e = _text(row.get("Knoten_E")) or _text(row.get("Point_E")) or (nodes[-1] if nodes else "")
    allow_a = _num(row.get("Aln_A")) or 0.0
    allow_e = _num(row.get("Aln_E")) or 0.0

    already_m = 0.0
    if status == STATUS_COMPLETE and nodes:
        done = calculate_pulled_length(route, node_a, allow_a, node_e, allow_e, nodes[0], nodes[-1])
        already_m = done.meters if done.ok else 0.0
    elif status == STATUS_PARTIAL and pulled_start and pulled_end and nodes:
        done = calculate_pulled_length(route, node_a, allow_a, node_e, allow_e, pulled_start, pulled_end)
        already_m = done.meters if done.ok else 0.0

    return {
        "kabelnr": _text(row.get("Kabelnr")),
        "status": status,
        "status_label": {
            STATUS_COMPLETE: "Teljesen behúzva",
            STATUS_PARTIAL: "Részlegesen behúzva",
            STATUS_NONE: "Nincs behúzás",
        }.get(status, status),
        "status_message": status_message,
        "verlegt_date": verlegt_date,
        "stop_date": stop_date,
        "pull_status": _text(row.get("Pull_status")),
        "route": route,
        "route_html": route_html,
        "route_missing": route_missing,
        "route_warning": route_warning,
        "pulled_start": pulled_start,
        "pulled_end": pulled_end,
        "already_pulled_m": already_m,
        "nodes": nodes,
        "distances": distances,
        "node_a": node_a,
        "node_e": node_e,
        "length_m": _num(row.get("Length_m")),
        "category": _text(row.get("Category")),
        "liste": _text(row.get("Liste")),
        "cable_type": cable_type,
        "adern": adern,
        "geraet_a": geraet_a,
        "geraet_e": geraet_e,
        "ort_a": ort_a,
        "ort_e": ort_e,
        "aln_a": aln_a,
        "aln_e": aln_e,
        "allowance_a": allow_a,
        "allowance_e": allow_e,
    }


def lookup_export_frame(details: list[dict]) -> pd.DataFrame:
    rows = []
    for d in details:
        rows.append(
            {
                "Kabelnr": d.get("kabelnr"),
                "Status": d.get("status_label"),
                "Behúzás / megállítás": d.get("verlegt_date") or d.get("stop_date") or "",
                "Liste": d.get("liste"),
                "Kábeltípus": d.get("cable_type"),
                "Adern / erek": d.get("adern"),
                "Category": d.get("category"),
                "Length_m": d.get("length_m"),
                "Geraet_A": d.get("geraet_a"),
                "Ort_A": d.get("ort_a"),
                "Aln_A": d.get("aln_a"),
                "Geraet_E": d.get("geraet_e"),
                "Ort_E": d.get("ort_e"),
                "Aln_E": d.get("aln_e"),
                "Behúzott_start": d.get("pulled_start"),
                "Behúzott_end": d.get("pulled_end"),
                "Nyomvonal": d.get("route"),
            }
        )
    return pd.DataFrame(rows)
