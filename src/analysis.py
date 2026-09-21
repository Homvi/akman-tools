from __future__ import annotations

import pandas as pd

from src.categories import CAT_LABELS

PULL_NOT = "Not pulled"
PULL_PARTIAL = "Részlegesen"
PULL_YES = "Pulled"
PULL_STATUSES = (PULL_NOT, PULL_PARTIAL, PULL_YES)
_EMPTY = {"", "<NA>", "nan", "None"}


def _has_startsegment(df: pd.DataFrame) -> pd.Series:
    flag = pd.Series(False, index=df.index)
    for slot in (1, 2, 3):
        col = f"Startsegment_{slot}"
        if col not in df.columns:
            continue
        text = df[col].astype("string").str.strip()
        flag = flag | (text.notna() & ~text.isin(_EMPTY))
    return flag


def assign_pull_status(df: pd.DataFrame) -> pd.DataFrame:
    if "Pull_status" in df.columns:
        return df
    out = df.copy()
    pulled = out["Pulled"].eq(True) if "Pulled" in out.columns else False
    started = _has_startsegment(out)
    status = pd.Series(PULL_NOT, index=out.index)
    status = status.mask(started, PULL_PARTIAL)
    status = status.mask(pulled, PULL_YES)
    out["Pull_status"] = status
    return out


def apply_filters(
    df: pd.DataFrame,
    *,
    devices: list[str] | None = None,
    pulled: list[str] | None = None,
    thickness: list[str] | None = None,
    categories: list[str] | None = None,
) -> pd.DataFrame:
    out = df if "Pull_status" in df.columns else assign_pull_status(df)
    if devices:
        device_set = set(devices)
        mask_a = out.get("Geraet_A", pd.Series("", index=out.index)).isin(device_set)
        mask_e = out.get("E_Geraet", pd.Series("", index=out.index)).isin(device_set)
        if "Geraet_E" in out.columns:
            mask_e = mask_e | out["Geraet_E"].isin(device_set)
        if "A_Geraet" in out.columns:
            mask_a = mask_a | out["A_Geraet"].isin(device_set)
        out = out[mask_a | mask_e]
    if pulled:
        out = out[out["Pull_status"].isin(pulled)]
    if thickness:
        out = out[out["Thickness"].isin(thickness)]
    if categories:
        out = out[out["Category"].isin(categories)]
    return out


def unique_devices(df: pd.DataFrame) -> list[str]:
    cols = [c for c in ("Geraet_A", "Geraet_E", "A_Geraet", "E_Geraet") if c in df.columns]
    values: set[str] = set()
    for col in cols:
        values.update(v for v in df[col].dropna().astype(str).str.strip() if v and v != "<NA>")
    return sorted(values)


def cable_numbers(df: pd.DataFrame) -> list[str]:
    if df.empty or "Kabelnr" not in df.columns:
        return []
    values = df["Kabelnr"].dropna().astype(str).str.strip()
    values = values[~values.isin(_EMPTY)]
    return sorted(dict.fromkeys(values), key=lambda item: (len(item), item))


def pulled_cables(df: pd.DataFrame) -> pd.DataFrame:
    out = assign_pull_status(df)
    return out[out["Pull_status"].eq(PULL_YES)]


def started_cables(df: pd.DataFrame) -> pd.DataFrame:
    out = assign_pull_status(df)
    return out[out["Pull_status"].eq(PULL_PARTIAL)]


def _liste_is(series: pd.Series, wanted: str) -> pd.Series:
    want = str(wanted).strip().lstrip("0") or "0"
    text = series.astype("string").str.strip()
    norm = text.str.replace(r"^0+", "", regex=True)
    norm = norm.fillna("").replace("", "0")
    return norm.eq(want)


def long_list_cables(df: pd.DataFrame, *, liste: str = "001", min_m: float = 150) -> pd.DataFrame:
    if df.empty or "Liste" not in df.columns or "Length_m" not in df.columns:
        return df.iloc[0:0].copy()
    length = pd.to_numeric(df["Length_m"], errors="coerce")
    return df.loc[_liste_is(df["Liste"], liste) & length.gt(min_m)].copy()


def _text_col(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series("", index=df.index, dtype="string")
    text = df[col].astype("string").str.strip()
    return text.where(text.notna() & ~text.isin(_EMPTY), "")


def cable_type_series(df: pd.DataFrame) -> pd.Series:
    typ = pd.Series("", index=df.index, dtype="string")
    for col in ("Kabeltyp", "Typ", "Artikel"):
        extra = _text_col(df, col)
        typ = typ.mask(typ.eq("") | typ.isna(), extra)
    adern = _text_col(df, "Kabeladern")
    labels = []
    for type_name, adern_name in zip(typ.fillna(""), adern.fillna("")):
        type_name = str(type_name).strip()
        adern_name = str(adern_name).strip()
        if type_name and adern_name:
            labels.append(f"{type_name} · Adern: {adern_name}")
        elif type_name:
            labels.append(type_name)
        elif adern_name:
            labels.append(f"Adern: {adern_name}")
        else:
            labels.append("Ismeretlen típus")
    return pd.Series(labels, index=df.index, dtype="string")


def cable_numbers_by_type(df: pd.DataFrame) -> dict[str, list[str]]:
    if df.empty:
        return {}
    types = cable_type_series(df)
    grouped = {}
    for label in sorted(types.unique(), key=str):
        numbers = cable_numbers(df.loc[types.eq(label)])
        if numbers:
            grouped[str(label)] = numbers
    return grouped


def counted_length(df: pd.DataFrame) -> pd.Series:
    """Full length for finished cables, pulled meters only for partial pulls."""
    out = assign_pull_status(df)
    length = pd.to_numeric(out.get("Length_m"), errors="coerce").fillna(0)
    pulled_m = pd.to_numeric(out.get("Total_teilgezogene_meter"), errors="coerce").fillna(0)
    counted = length.copy()
    counted = counted.mask(out["Pull_status"].eq(PULL_PARTIAL), pulled_m)
    return counted


def total_length(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    return float(counted_length(df).sum())


def _node_name(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text in _EMPTY else text.upper()


def _is_finished_cable(cable: pd.Series) -> bool:
    if cable.get("Pull_status") == PULL_YES or cable.get("Pulled") is True:
        return True
    if pd.notna(cable.get("verlegt")):
        return True
    remaining = pd.to_numeric(cable.get("Remaining_m"), errors="coerce")
    return pd.notna(remaining) and float(remaining) <= 0


def _final_nodes(cable: pd.Series) -> set[str]:
    nodes = {
        _node_name(cable.get("Point_A")),
        _node_name(cable.get("Point_E")),
        _node_name(cable.get("Knoten_A")),
        _node_name(cable.get("Knoten_E")),
    }
    path = cable.get("Path_nodes")
    if isinstance(path, (list, tuple)) and path:
        nodes.add(_node_name(path[0]))
        nodes.add(_node_name(path[-1]))
    nodes.discard("")
    return nodes


def _latest_stop_slot(cable: pd.Series) -> int | None:
    best: tuple[pd.Timestamp, int] | None = None
    for slot in (1, 2, 3):
        stopped = cable.get(f"Gestoppt_{slot}")
        if pd.isna(stopped):
            continue
        when = pd.Timestamp(stopped)
        if best is None or when > best[0] or (when == best[0] and slot > best[1]):
            best = (when, slot)
    return None if best is None else best[1]


def _stop_location_for_slot(cable: pd.Series, slot: int) -> str:
    location = cable.get(f"Endsegment_{slot}")
    if pd.isna(location) or str(location).strip() in _EMPTY:
        location = cable.get(f"Startsegment_{slot}")
    if pd.isna(location) or str(location).strip() in _EMPTY:
        return "Unknown"
    return str(location).strip()


def stopped_by_location(df: pd.DataFrame) -> pd.DataFrame:
    """Current stop only: last Gestoppt, skip finished cables and final A/E holes."""
    rows = []
    for _, cable in df.iterrows():
        if _is_finished_cable(cable):
            continue
        slot = _latest_stop_slot(cable)
        if slot is None:
            continue
        location = _stop_location_for_slot(cable, slot)
        if _node_name(location) in _final_nodes(cable):
            continue
        stopped = cable.get(f"Gestoppt_{slot}")
        rows.append(
            {
                "Stop_location": location,
                "join_key": cable.get("join_key"),
                "Kabelnr": cable.get("Kabelnr"),
                "Category": cable.get("Category"),
                "Thickness": cable.get("Thickness"),
                "Liste": cable.get("Liste"),
                "Geraet_A": cable.get("Geraet_A") if pd.notna(cable.get("Geraet_A")) else cable.get("A_Geraet"),
                "Geraet_E": cable.get("Geraet_E") if pd.notna(cable.get("Geraet_E")) else cable.get("E_Geraet"),
                "Length_m": cable.get("Length_m"),
                "Pulled_at_stop_m": cable.get(f"Teilgezogene_meter_{slot}"),
                "Total_pulled_m": cable.get("Total_teilgezogene_meter"),
                "Remaining_m": cable.get("Remaining_m"),
                "Gestoppt": stopped,
                "Startsegment": cable.get(f"Startsegment_{slot}"),
                "Endsegment": cable.get(f"Endsegment_{slot}"),
                "Pfad": cable.get("Pfad"),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "Stop_location",
                "join_key",
                "Kabelnr",
                "Category",
                "Thickness",
                "Liste",
                "Geraet_A",
                "Geraet_E",
                "Length_m",
                "Pulled_at_stop_m",
                "Total_pulled_m",
                "Remaining_m",
                "Gestoppt",
                "Startsegment",
                "Endsegment",
                "Pfad",
            ]
        )
    return pd.DataFrame(rows)


def aggregate_stops(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame(
            columns=[
                "Stop_location",
                "Cable_count",
                "Cables",
                "Remaining_unpulled_m",
                "Total_cable_length_m",
                "Pulled_at_this_stop_m",
            ]
        )
    grouped = (
        detail.groupby("Stop_location", dropna=False)
        .agg(
            Cable_count=("Kabelnr", "nunique"),
            Cables=("Kabelnr", lambda s: ", ".join(sorted({str(v) for v in s if pd.notna(v)}))),
            Remaining_unpulled_m=("Remaining_m", "sum"),
            Total_cable_length_m=("Length_m", "sum"),
            Pulled_at_this_stop_m=("Pulled_at_stop_m", "sum"),
        )
        .reset_index()
        .sort_values(["Cable_count", "Stop_location"], ascending=[False, True])
    )
    return grouped


def available_categories(df: pd.DataFrame) -> list[str]:
    present = set(df.get("Category", pd.Series(dtype=str)).dropna().astype(str))
    ordered = [label for label in CAT_LABELS if label in present]
    extra = sorted(present - set(CAT_LABELS))
    return ordered + extra
