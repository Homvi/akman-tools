from __future__ import annotations

import re
import unicodedata
from io import BytesIO
from typing import BinaryIO

import pandas as pd

from src.categories import extract_k_category, thickness_label
from src.dates import series_to_dates
from src.ids import join_key, normalize_kabel_id

_CABLE_ID = re.compile(r"^\s*\d")

_STATUS_ALIASES = {
    "stat": "Stat",
    "kabelnr": "Kabelnr",
    "kabelbez.(ext.)": "Kabelbez_ext",
    "kabelbez(ext)": "Kabelbez_ext",
    "kabeltyp": "Kabeltyp",
    "kabeladern": "Kabeladern",
    "a.gerat": "A_Geraet",
    "a.geraet": "A_Geraet",
    "e.gerat": "E_Geraet",
    "e.geraet": "E_Geraet",
    "a.ort": "A_Ort",
    "e.ort": "E_Ort",
    "liste": "Liste",
    "zuschn.": "Zuschn",
    "zuschn": "Zuschn",
    "verlegt": "verlegt",
    "bemerkung": "Bemerkung",
    "startsegment_1": "Startsegment_1",
    "endsegment_1": "Endsegment_1",
    "gestoppt_1": "Gestoppt_1",
    "teilgezogene meter_1": "Teilgezogene_meter_1",
    "startsegment_2": "Startsegment_2",
    "endsegment_2": "Endsegment_2",
    "gestoppt_2": "Gestoppt_2",
    "teilgezogene meter_2": "Teilgezogene_meter_2",
    "startsegment_3": "Startsegment_3",
    "endsegment_3": "Endsegment_3",
    "gestoppt_3": "Gestoppt_3",
    "teilgezogene meter_3": "Teilgezogene_meter_3",
    "total_teilgezogene_meter": "Total_teilgezogene_meter",
    "note": "Note",
}

_METER_COLS = (
    "Teilgezogene_meter_1",
    "Teilgezogene_meter_2",
    "Teilgezogene_meter_3",
    "Zuschn",
)


def _norm_header(value) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()


def _as_excel(source: str | BytesIO | BinaryIO):
    if hasattr(source, "seek"):
        source.seek(0)
    return source


def parse_status_list(source: str | BytesIO | BinaryIO) -> pd.DataFrame:
    raw = pd.read_excel(_as_excel(source), sheet_name=0, engine="openpyxl")
    rename = {}
    for col in raw.columns:
        key = _norm_header(col)
        if key in _STATUS_ALIASES:
            rename[col] = _STATUS_ALIASES[key]
    df = raw.rename(columns=rename).copy()

    if "Kabelnr" not in df.columns:
        raise ValueError("Status list is missing column Kabelnr.")

    df["Kabelnr"] = df["Kabelnr"].map(normalize_kabel_id)
    df["join_key"] = df["Kabelnr"].map(join_key)
    df = df[df["join_key"] != ""].copy()

    if "verlegt" in df.columns:
        df["verlegt"] = series_to_dates(df["verlegt"])
    else:
        df["verlegt"] = pd.NaT

    for slot in (1, 2, 3):
        gcol = f"Gestoppt_{slot}"
        if gcol in df.columns:
            df[gcol] = series_to_dates(df[gcol])
        else:
            df[gcol] = pd.NaT
        for prefix in ("Startsegment", "Endsegment"):
            col = f"{prefix}_{slot}"
            if col not in df.columns:
                df[col] = pd.NA
            else:
                df[col] = df[col].astype("string").str.strip()
                df[col] = df[col].replace({"": pd.NA, "nan": pd.NA, "<NA>": pd.NA})
        mcol = f"Teilgezogene_meter_{slot}"
        if mcol not in df.columns:
            df[mcol] = pd.NA
        df[mcol] = pd.to_numeric(df[mcol], errors="coerce")

    for col in _METER_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    meters = df[list(_METER_COLS[:3])].sum(axis=1, min_count=1)
    if "Total_teilgezogene_meter" in df.columns:
        existing = pd.to_numeric(df["Total_teilgezogene_meter"], errors="coerce")
        df["Total_teilgezogene_meter"] = existing.fillna(meters)
    else:
        df["Total_teilgezogene_meter"] = meters

    df["Pulled"] = df["verlegt"].notna()
    for col in ("A_Geraet", "E_Geraet", "Liste", "Kabeltyp", "Kabeladern", "Bemerkung", "Note"):
        if col not in df.columns:
            df[col] = pd.NA
        else:
            df[col] = df[col].astype("string").str.strip()
    return df.reset_index(drop=True)


def parse_catra_list(source: str | BytesIO | BinaryIO) -> pd.DataFrame:
    raw = pd.read_excel(_as_excel(source), sheet_name=0, header=None, engine="openpyxl")
    start = _first_block_row(raw)
    header_rows = [_row_values(raw.iloc[i]) for i in range(start)]
    records = []
    for idx in range(start, len(raw), 4):
        block = raw.iloc[idx : idx + 4]
        if len(block) < 4:
            break
        record = _flatten_catra_block(block)
        if record:
            record["_block"] = [_row_values(block.iloc[r]) for r in range(len(block))]
            records.append(record)
    if not records:
        raise ValueError("No 4-row CaTra cable blocks were found.")
    out = pd.DataFrame.from_records(records)
    out.attrs["catra_header"] = header_rows
    return out


def _first_block_row(raw: pd.DataFrame) -> int:
    for i, value in enumerate(raw.iloc[:, 0].tolist()):
        if value is not None and not (isinstance(value, float) and pd.isna(value)):
            if _CABLE_ID.match(str(value)):
                return i
    raise ValueError("Could not find the first CaTra cable block.")


def _row_values(row: pd.Series) -> list:
    values = []
    for value in row.tolist():
        if value is None or (isinstance(value, float) and pd.isna(value)):
            values.append(None)
        else:
            values.append(value)
    while values and values[-1] is None:
        values.pop()
    return values


def _cell(block: pd.DataFrame, row: int, col: int) -> str:
    if row >= len(block) or col >= block.shape[1]:
        return ""
    value = block.iat[row, col]
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _flatten_catra_block(block: pd.DataFrame) -> dict | None:
    kabel_raw = _cell(block, 0, 0)
    if not kabel_raw or not _CABLE_ID.match(kabel_raw):
        return None

    laenge = pd.to_numeric(_cell(block, 0, 3).replace(",", ".") or None, errors="coerce")
    path_cells = [str(v).strip() for v in block.iloc[3].tolist() if pd.notna(v) and str(v).strip()]
    geraet_a = _cell(block, 0, 9)
    geraet_e = _cell(block, 1, 9)
    devices = [part for part in (geraet_a, geraet_e) if part]

    return {
        "Kabel_raw": kabel_raw,
        "Kabel": normalize_kabel_id(kabel_raw),
        "join_key": join_key(kabel_raw),
        "Category": extract_k_category(kabel_raw),
        "Artikel": _cell(block, 0, 1),
        "Liste": _cell(block, 1, 1),
        "Typ": _cell(block, 0, 2),
        "Laenge": laenge,
        "Knoten_A": _cell(block, 0, 6),
        "Aln_A": _cell(block, 0, 7),
        "Ort_A": _cell(block, 0, 8),
        "Geraet_A": geraet_a,
        "Knoten_E": _cell(block, 1, 6),
        "Aln_E": _cell(block, 1, 7),
        "Ort_E": _cell(block, 1, 8),
        "Geraet_E": geraet_e,
        "Geraet": " | ".join(devices),
        "Knoten_Z": _cell(block, 2, 6),
        "Notizen": _cell(block, 2, 0),
        "Pfad": " ".join(path_cells),
        "Kabelbez": _cell(block, 1, 0),
        "Thickness": thickness_label(_cell(block, 0, 2)),
    }
