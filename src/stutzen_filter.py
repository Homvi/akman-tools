from __future__ import annotations

import html
import re

import pandas as pd

from src.analysis import PULL_NOT, PULL_PARTIAL, PULL_YES, assign_pull_status
from src.export import DEFAULT_CATRA_HEADER, _plain_path
from src.length_calc import has_verlegt_date, latest_pull_ends

MODE_AND = "AND"
MODE_OR = "OR"
MODE_LABELS = {MODE_AND: "MIND (AND)", MODE_OR: "BÁRMELYIK (OR)"}

# Pull-status filter keys used by the web UI (stable API values).
STATUS_NOT_STARTED = "not_started"
STATUS_STARTED = "started"
STATUS_FULL = "fully_pulled"
STATUS_KEYS = (STATUS_NOT_STARTED, STATUS_STARTED, STATUS_FULL)
STATUS_TO_PULL = {
    STATUS_NOT_STARTED: PULL_NOT,
    STATUS_STARTED: PULL_PARTIAL,
    STATUS_FULL: PULL_YES,
}
PULL_TO_STATUS = {v: k for k, v in STATUS_TO_PULL.items()}

# Selectable export columns: (api_key, excel_header, source column or derived)
EXPORT_COLUMNS: list[tuple[str, str, str]] = [
    ("kabelnr", "Kabelnr", "Kabelnr"),
    ("liste", "Liste", "Liste"),
    ("category", "Category", "Category"),
    ("thickness", "Thickness", "Thickness"),
    ("length_m", "Length_m", "Length_m"),
    ("pull_status", "Pull_status", "Pull_status"),
    ("stop_location", "Megállítás", "Megállítás"),
    ("stop_locations", "Megállítások", "Megállítások"),
    ("geraet_a", "Geraet_A", "Geraet_A"),
    ("geraet_e", "Geraet_E", "Geraet_E"),
    ("ort_a", "Ort_A", "Ort_A"),
    ("ort_e", "Ort_E", "Ort_E"),
    ("verlegt", "verlegt", "verlegt"),
    ("pfad", "Nyomvonal", "Pfad"),
]
EXPORT_COLUMN_KEYS = [key for key, _, _ in EXPORT_COLUMNS]
DEFAULT_EXPORT_COLUMNS = [
    "kabelnr",
    "liste",
    "category",
    "length_m",
    "pull_status",
    "stop_locations",
    "geraet_a",
    "geraet_e",
    "ort_a",
    "ort_e",
    "verlegt",
]

_PAREN = re.compile(r"\s*\([^)]*\)")
_SAFE_FILE = re.compile(r"[^a-zA-Z0-9._-]")
_SPLIT_NODES = re.compile(r"[;,\n]+")


def parse_search_nodes(text, *, unique_only: bool = False) -> list[str]:
    """
    Parse Stütze / Bahn numbers separated by semicolon, comma, or newline.
    When unique_only=True, keep first occurrence of each token.
    """
    raw = str(text or "").strip()
    if not raw:
        return []
    nodes: list[str] = []
    seen: set[str] = set()
    for part in _SPLIT_NODES.split(raw):
        token = part.strip()
        if not token:
            continue
        if unique_only:
            key = token.casefold()
            if key in seen:
                continue
            seen.add(key)
        nodes.append(token)
    return nodes


def search_nodes_stats(text) -> dict:
    raw = parse_search_nodes(text, unique_only=False)
    unique = parse_search_nodes(text, unique_only=True)
    counts: dict[str, int] = {}
    for token in raw:
        key = token.casefold()
        counts[key] = counts.get(key, 0) + 1
    duplicates = []
    seen_dup: set[str] = set()
    for token in raw:
        key = token.casefold()
        if counts.get(key, 0) > 1 and key not in seen_dup:
            duplicates.append(token)
            seen_dup.add(key)
    return {
        "raw": raw,
        "unique": unique,
        "raw_count": len(raw),
        "unique_count": len(unique),
        "duplicate_count": len(raw) - len(unique),
        "duplicates": duplicates,
    }


def route_node_set(pfad) -> set[str]:
    if pfad is None:
        return set()
    try:
        if pd.isna(pfad):
            return set()
    except (TypeError, ValueError):
        pass
    cleaned = _PAREN.sub(" ", str(pfad))
    return {token for token in cleaned.split() if token}


def route_node_set_folded(pfad) -> set[str]:
    return {token.casefold() for token in route_node_set(pfad)}


def route_matches(pfad, nodes: list[str], mode: str) -> bool:
    if not nodes:
        return False
    found = route_node_set_folded(pfad)
    needles = [str(node).casefold() for node in nodes if str(node).strip()]
    if not needles:
        return False
    if str(mode).upper() == MODE_AND:
        return all(node in found for node in needles)
    return any(node in found for node in needles)


def cable_route(row: pd.Series) -> str:
    return _plain_path(row)


def cable_length(row: pd.Series) -> float:
    for col in ("Laenge", "Length_m"):
        if col not in row.index:
            continue
        value = pd.to_numeric(row.get(col), errors="coerce")
        if pd.notna(value):
            return float(value)
    return 0.0


def filter_by_nodes(df: pd.DataFrame, nodes: list[str], mode: str) -> pd.DataFrame:
    if df is None or df.empty or not nodes or "Pfad" not in df.columns:
        return df.iloc[0:0].copy() if df is not None else pd.DataFrame()
    mask = df["Pfad"].map(lambda pfad: route_matches(pfad, nodes, mode))
    return df.loc[mask].copy()


def pull_status_counts(df: pd.DataFrame) -> dict[str, int]:
    """Counts for not_started / started / fully_pulled on a node-filtered frame."""
    empty = {STATUS_NOT_STARTED: 0, STATUS_STARTED: 0, STATUS_FULL: 0}
    if df is None or df.empty:
        return empty
    frame = assign_pull_status(df)
    counts = frame["Pull_status"].value_counts()
    return {
        STATUS_NOT_STARTED: int(counts.get(PULL_NOT, 0)),
        STATUS_STARTED: int(counts.get(PULL_PARTIAL, 0)),
        STATUS_FULL: int(counts.get(PULL_YES, 0)),
    }


def thickness_counts(df: pd.DataFrame) -> dict[str, int]:
    """Thick / Thin / Unknown cable counts on a node-filtered frame."""
    empty = {"thick": 0, "thin": 0, "unknown": 0}
    if df is None or df.empty or "Thickness" not in df.columns:
        return empty
    series = df["Thickness"].astype(str).str.strip().str.casefold()
    thick = int((series == "thick").sum())
    thin = int((series == "thin").sum())
    return {
        "thick": thick,
        "thin": thin,
        "unknown": max(int(len(df)) - thick - thin, 0),
    }


def normalize_status_keys(statuses: list[str] | None) -> list[str]:
    if not statuses:
        return list(STATUS_KEYS)
    out: list[str] = []
    seen: set[str] = set()
    for raw in statuses:
        key = str(raw or "").strip().casefold()
        # Accept both UI keys and raw Pull_status labels.
        mapped = None
        for status_key in STATUS_KEYS:
            if key == status_key or key == STATUS_TO_PULL[status_key].casefold():
                mapped = status_key
                break
        if mapped is None:
            continue
        if mapped not in seen:
            seen.add(mapped)
            out.append(mapped)
    return out or list(STATUS_KEYS)


def filter_by_pull_statuses(df: pd.DataFrame, statuses: list[str] | None) -> pd.DataFrame:
    if df is None or df.empty:
        return df.iloc[0:0].copy() if df is not None else pd.DataFrame()
    keys = normalize_status_keys(statuses)
    if set(keys) == set(STATUS_KEYS):
        return assign_pull_status(df)
    wanted = {STATUS_TO_PULL[k] for k in keys}
    frame = assign_pull_status(df)
    return frame.loc[frame["Pull_status"].isin(wanted)].copy()


def format_pulled_span(row: pd.Series) -> str:
    """Current pulled segment only: first Startsegment → latest Endsegment.

    Fully verlegt cables leave Megállítás empty even if Start/End remain filled.
    """
    if has_verlegt_date(row):
        return ""
    start, end = latest_pull_ends(row)
    if not start and not end:
        return ""
    return f"{start} → {end}"


def enrich_stutzen_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Add Pull_status + current pull-span columns for preview/export."""
    if df is None or df.empty:
        return df.iloc[0:0].copy() if df is not None else pd.DataFrame()
    out = assign_pull_status(df)
    span = out.apply(format_pulled_span, axis=1)
    out["Megállítás"] = span
    out["Megállítások"] = span
    return out


def export_column_catalog() -> list[dict[str, str]]:
    return [{"key": key, "label": label} for key, label, _ in EXPORT_COLUMNS]


def select_export_columns(df: pd.DataFrame, column_keys: list[str] | None) -> pd.DataFrame:
    frame = enrich_stutzen_frame(df)
    keys = [k for k in (column_keys or DEFAULT_EXPORT_COLUMNS) if k in EXPORT_COLUMN_KEYS]
    if not keys:
        keys = list(DEFAULT_EXPORT_COLUMNS)
    cols: list[str] = []
    rename: dict[str, str] = {}
    for key, header, source in EXPORT_COLUMNS:
        if key not in keys:
            continue
        if source not in frame.columns:
            frame[source] = ""
        cols.append(source)
        rename[source] = header
    slim = frame[cols].copy()
    return slim.rename(columns=rename)


def preview_rows(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "name": _first(row, "Kabel_raw", "Kabelnr") or "Ismeretlen kábel",
                "code": _first(row, "Kabelbez", "Liste") or "",
                "type": _first(row, "Typ", "Kabeladern", "Artikel") or "",
                "length": cable_length(row),
                "route": cable_route(row),
            }
        )
    return rows


def total_preview_length(rows: list[dict]) -> float:
    return sum(float(row.get("length") or 0) for row in rows)


def stutzen_filename(nodes: list[str]) -> str:
    clean = "_".join(nodes)
    clean = _SAFE_FILE.sub("", clean) or "szures"
    return f"stutzen_{clean}.xlsx"


def criteria_header(base, nodes: list[str], mode: str) -> list[list]:
    header = [list(row) for row in (base or DEFAULT_CATRA_HEADER)]
    if not header:
        header = [list(row) for row in DEFAULT_CATRA_HEADER]
    if not header[0]:
        header[0] = [None]
    header[0][0] = f"Szűrési kritériumok: {', '.join(nodes)} ({mode})"
    return header


def highlight_route(text, nodes: list[str]) -> str:
    escaped = html.escape("" if text is None else str(text))
    sorted_nodes = sorted((n for n in nodes if n), key=len, reverse=True)
    for node in sorted_nodes:
        pattern = rf"(?<![a-zA-Z0-9.])({re.escape(html.escape(node))})(?![a-zA-Z0-9.])"
        escaped = re.sub(
            pattern,
            r'<mark style="background:#facc15;color:#0f172a;font-weight:800;padding:2px 6px;border-radius:4px;">\1</mark>',
            escaped,
        )
    return escaped


def preview_cards_html(rows: list[dict], nodes: list[str]) -> str:
    if not rows:
        return (
            '<div style="font-family:Segoe UI,sans-serif;color:#94a3b8;padding:24px;text-align:center;">'
            "Nincs a szűrésnek megfelelő kábel.</div>"
        )
    cards = []
    for row in rows:
        cards.append(
            f"""
            <div style="border:1px solid #334155;border-radius:12px;padding:14px;margin-bottom:10px;background:#0f172a;">
              <div style="display:flex;justify-content:space-between;gap:12px;font-size:13px;">
                <div>
                  <span style="color:#facc15;font-weight:700;font-family:Consolas,monospace;">{html.escape(str(row["name"]))}</span>
                  <span style="color:#94a3b8;"> | Kód: <strong style="color:#e2e8f0;">{html.escape(str(row["code"]))}</strong></span>
                  <span style="color:#64748b;"> ({html.escape(str(row["type"]))})</span>
                </div>
                <span style="color:#34d399;font-weight:700;white-space:nowrap;">{row["length"]:.1f} m</span>
              </div>
              <div style="margin-top:8px;background:#020617;border:1px solid #1e293b;border-radius:8px;padding:10px;
                          font-family:Consolas,monospace;font-size:12px;color:#cbd5e1;line-height:1.55;white-space:pre-wrap;">
                {highlight_route(row["route"], nodes)}
              </div>
            </div>
            """
        )
    return (
        '<div style="font-family:Segoe UI,sans-serif;max-height:600px;overflow:auto;padding-right:6px;">'
        + "".join(cards)
        + "</div>"
    )


def _first(row: pd.Series, *names) -> str:
    for name in names:
        if name not in row.index:
            continue
        value = row.get(name)
        if value is None:
            continue
        try:
            if pd.isna(value):
                continue
        except (TypeError, ValueError):
            pass
        text = str(value).strip()
        if text and text.lower() not in {"nan", "<na>", "none"}:
            return text
    return ""
