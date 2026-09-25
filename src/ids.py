from __future__ import annotations

import re

import pandas as pd

_SUFFIX = re.compile(r"\s*\(([ES])\)\s*(K\d+)?\s*$", re.IGNORECASE)
_SPLIT_IDS = re.compile(r"[;\n]+")


def normalize_kabel_id(value) -> str:
    """Turn 0002 (E) K3 or numeric 2114.1 into a stable id like 0002 / 2114,1."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if float(value).is_integer():
            text = str(int(value))
        else:
            text = str(value).replace(".", ",")
    else:
        text = str(value).strip()

    text = _SUFFIX.sub("", text).strip()
    text = re.sub(r"\.(\d+)$", r",\1", text)
    return text


def join_key(value) -> str:
    """Match 0002 to 2 and 0002,1 to 2,1 without dropping the sub-id."""
    text = normalize_kabel_id(value)
    if not text:
        return ""
    if "," in text:
        main, rest = text.split(",", 1)
        return f"{_strip_zeros(main)},{rest}"
    return _strip_zeros(text)


def _strip_zeros(token: str) -> str:
    stripped = token.lstrip("0")
    return stripped or "0"


def parse_cable_id_list(text, *, dedupe: bool = True) -> list[str]:
    """
    Parse semicolon / newline / comma-separated cable IDs.
    Keeps input order; 5012.1 and 5012,1 become the same join_key.
    When dedupe=True (default), first occurrence wins.
    """
    raw = str(text or "").strip()
    if not raw:
        return []
    seen: set[str] = set()
    keys: list[str] = []
    for part in _SPLIT_IDS.split(raw):
        token = part.strip().strip(",")
        if not token:
            continue
        key = join_key(token)
        if not key:
            continue
        if dedupe:
            if key in seen:
                continue
            seen.add(key)
        keys.append(key)
    return keys


def cable_id_list_stats(text) -> dict:
    """Raw vs unique IDs and which keys were repeated in the paste."""
    raw_keys = parse_cable_id_list(text, dedupe=False)
    unique_keys = parse_cable_id_list(text, dedupe=True)
    counts: dict[str, int] = {}
    for key in raw_keys:
        counts[key] = counts.get(key, 0) + 1
    duplicates = [key for key, n in counts.items() if n > 1]
    return {
        "raw": raw_keys,
        "unique": unique_keys,
        "raw_count": len(raw_keys),
        "unique_count": len(unique_keys),
        "duplicate_count": len(raw_keys) - len(unique_keys),
        "duplicates": duplicates,
        "counts": counts,
    }


def select_cables_by_ids(
    df: pd.DataFrame,
    id_text,
    *,
    dedupe: bool = True,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """
    Select cables whose join_key matches the pasted ID list.
    Returns (matched_rows in request order, found_keys, missing_keys).
    """
    wanted = parse_cable_id_list(id_text, dedupe=dedupe)
    if df is None or df.empty or not wanted:
        empty = df.iloc[0:0].copy() if df is not None else pd.DataFrame()
        return empty, [], wanted

    if "join_key" not in df.columns:
        empty = df.iloc[0:0].copy()
        return empty, [], wanted

    unique = df.drop_duplicates(subset=["join_key"], keep="first")
    by_key = {str(key): unique.loc[idx] for idx, key in zip(unique.index, unique["join_key"].astype(str))}
    rows = []
    found: list[str] = []
    missing: list[str] = []
    seen_found: set[str] = set()
    for key in wanted:
        row = by_key.get(key)
        if row is None:
            if key not in missing:
                missing.append(key)
            continue
        if dedupe and key in seen_found:
            continue
        seen_found.add(key)
        found.append(key)
        rows.append(row)
    matched = pd.DataFrame(rows) if rows else df.iloc[0:0].copy()
    return matched, found, missing
