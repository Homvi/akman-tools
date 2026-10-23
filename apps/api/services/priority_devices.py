from __future__ import annotations

import pandas as pd

from apps.api.services.dataset import _find_col, _has_date_series
from apps.api.services.device_stats import (
    device_pull_stats,
    device_sides,
    side_pulled_to_device,
    _same_device,
    _text,
)
from src.analysis import assign_pull_status, unique_devices
from src.stutzen_filter import filter_by_pull_statuses

# Names as in Progressliste Geraet_A / Geraet_E (English). Photo DE → EN mapping.
PRIORITY_DEVICE_NAMES: list[str] = [
    "44b AMS Cabinet 1 Bow",
    "10.1 Battery Box 24V DC Bow",
    "10 Main Distribution 24V DC Bow",
    "2 Main Switchboard Bow",  # photo: Hauptverteilung BUG
    "49 Converter Distribution Bow",
    "9.1 Battery Box 24V DC Stern",
    "9 Main Distribution 24V DC Stern",
    "1a Main Distribution Stern",
    "67 Converter Distribution Stern",
    "44a AMS Cabinet 2 Stern",
    "193 Emergency Switchboard",
    "26 Shore Connection SB",
    "26a Ship Ship Supply SB",
    "25 Shore Connection PS",
    "25a Ship Ship Supply PS",
    "44 AMS Cabinet 3 ECR",
    "1 Main Switchboard Stern",
    "3 Emergency Distribution Stern",
    "8.1 Battery Box 24V DC Mid",
    "8 Main Distribution 24V DC Mid",
]


def _anschluss_cols(df: pd.DataFrame) -> tuple[str | None, str | None]:
    col_a = (
        _find_col(df, "anschluss", "1")
        or ("Anschluss_1" if "Anschluss_1" in df.columns else None)
        or ("Anschluss 1" if "Anschluss 1" in df.columns else None)
    )
    col_e = (
        _find_col(df, "anschluss", "2")
        or ("Anschluss_2" if "Anschluss_2" in df.columns else None)
        or ("Anschluss 2" if "Anschluss 2" in df.columns else None)
    )
    return col_a, col_e


def cables_for_device(df: pd.DataFrame, device: str) -> pd.DataFrame:
    name = _text(device)
    if df is None or df.empty or not name:
        return df.iloc[0:0].copy() if df is not None else pd.DataFrame()
    mask_a = df.apply(lambda row: _same_device(row.get("Geraet_A") or row.get("A_Geraet"), name), axis=1)
    mask_e = df.apply(lambda row: _same_device(row.get("Geraet_E") or row.get("E_Geraet"), name), axis=1)
    return df.loc[mask_a | mask_e].copy()


def cables_for_devices(df: pd.DataFrame, devices: list[str]) -> pd.DataFrame:
    names = [_text(d) for d in devices if _text(d)]
    if df is None or df.empty or not names:
        return df.iloc[0:0].copy() if df is not None else pd.DataFrame()
    name_set = set(names)

    def touches(row: pd.Series) -> bool:
        a = _text(row.get("Geraet_A") or row.get("A_Geraet"))
        e = _text(row.get("Geraet_E") or row.get("E_Geraet"))
        return (a in name_set) or (e in name_set)

    mask = df.apply(touches, axis=1)
    return df.loc[mask].copy()


def device_priority_stats(df: pd.DataFrame, device: str) -> dict:
    """Per-device totals: wired (Anschluss) and pulled-to-device, with A/E breakdown."""
    name = _text(device)
    empty = {
        "name": name,
        "matched": False,
        "total": 0,
        "wired": 0,
        "wired_a": 0,
        "wired_e": 0,
        "pulled": 0,
        "pulled_a": 0,
        "pulled_e": 0,
        "device_at": 0,
        "device_started": 0,
        "device_not_started": 0,
    }
    if not name:
        return empty

    known = {_text(d) for d in unique_devices(df)} if df is not None and not df.empty else set()
    matched = name in known
    part = cables_for_device(df, name)
    if part.empty:
        return {**empty, "matched": matched}

    col_a, col_e = _anschluss_cols(part)
    has_a = _has_date_series(part[col_a]) if col_a else pd.Series(False, index=part.index)
    has_e = _has_date_series(part[col_e]) if col_e else pd.Series(False, index=part.index)

    wired_a = wired_e = pulled_a = pulled_e = 0
    for idx, row in part.iterrows():
        sides = device_sides(row, name)
        if "A" in sides:
            if bool(has_a.at[idx]):
                wired_a += 1
            if side_pulled_to_device(row, "A"):
                pulled_a += 1
        if "E" in sides:
            if bool(has_e.at[idx]):
                wired_e += 1
            if side_pulled_to_device(row, "E"):
                pulled_e += 1

    # Cable counts: wired/pulled if the device-facing side(s) satisfy the condition.
    wired = pulled = 0
    for idx, row in part.iterrows():
        sides = device_sides(row, name)
        if not sides:
            continue
        if all(
            (s == "A" and bool(has_a.at[idx])) or (s == "E" and bool(has_e.at[idx])) for s in sides
        ):
            wired += 1
        if all(side_pulled_to_device(row, s) for s in sides):
            pulled += 1

    progress = device_pull_stats(part, name)
    return {
        "name": name,
        "matched": matched,
        "total": int(len(part)),
        "wired": int(wired),
        "wired_a": int(wired_a),
        "wired_e": int(wired_e),
        "pulled": int(pulled),
        "pulled_a": int(pulled_a),
        "pulled_e": int(pulled_e),
        "device_at": int(progress.get("device_at") or 0),
        "device_started": int(progress.get("device_started") or 0),
        "device_not_started": int(progress.get("device_not_started") or 0),
    }


def priority_devices_summary(df: pd.DataFrame | None) -> list[dict]:
    frame = assign_pull_status(df) if df is not None and not df.empty else pd.DataFrame()
    return [device_priority_stats(frame, name) for name in PRIORITY_DEVICE_NAMES]


def priority_export_frame(
    df: pd.DataFrame,
    *,
    devices: list[str] | None = None,
    statuses: list[str] | None = None,
) -> pd.DataFrame:
    names = devices if devices else list(PRIORITY_DEVICE_NAMES)
    names = [_text(n) for n in names if _text(n)]
    frame = assign_pull_status(df)
    hits = cables_for_devices(frame, names)
    return filter_by_pull_statuses(hits, statuses or [])
