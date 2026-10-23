from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd

from apps.api.config import settings
from src.dates import is_pulled
from src.ids import normalize_kabel_id
from src.parsers import parse_status_list

_UPLOAD_NAME = "live_progressliste.xlsx"
_PARQUET_NAME = "live_progressliste.parquet"
_META_NAME = "live_progressliste_meta.json"


def _upload_path() -> Path:
    return settings.appdata_path / "uploads" / _UPLOAD_NAME


def _parquet_path() -> Path:
    return settings.appdata_path / "datasets" / _PARQUET_NAME


def _meta_path() -> Path:
    return settings.appdata_path / "datasets" / _META_NAME


def _norm_kabelnr(value) -> str:
    text = "" if value is None else str(value).strip()
    if not text or text.lower() in {"nan", "<na>", "none", "nat"}:
        return ""
    return normalize_kabel_id(text) or text


def _slim_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["Kabelnr", "verlegt", "join_key"])
    out = pd.DataFrame()
    out["Kabelnr"] = df["Kabelnr"].map(_norm_kabelnr) if "Kabelnr" in df.columns else ""
    out["verlegt"] = df["verlegt"] if "verlegt" in df.columns else None
    if "join_key" in df.columns:
        out["join_key"] = df["join_key"].astype(str)
    else:
        out["join_key"] = out["Kabelnr"]
    out = out[out["Kabelnr"].astype(str).str.len() > 0].copy()
    return out.reset_index(drop=True)


def save_live_progressliste(data: bytes, *, file_name: str = "") -> dict:
    """Parse Progressliste bytes, persist parquet + meta, return status dict."""
    raw = parse_status_list(BytesIO(data))
    slim = _slim_frame(raw)
    upload = _upload_path()
    upload.write_bytes(data)
    parquet = _parquet_path()
    slim.to_parquet(parquet, index=False)
    verlegt_count = int(sum(1 for v in slim["verlegt"] if is_pulled(v))) if not slim.empty else 0
    meta = {
        "loaded": True,
        "file_name": file_name or upload.name,
        "cable_count": int(len(slim)),
        "verlegt_count": verlegt_count,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    _meta_path().write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta


def load_live_frame() -> pd.DataFrame | None:
    path = _parquet_path()
    if not path.exists():
        return None
    return pd.read_parquet(path)


def load_live_verlegt_keys() -> set[str]:
    """Normalized Kabelnr values that have a real verlegt date in the live overlay."""
    frame = load_live_frame()
    if frame is None or frame.empty or "Kabelnr" not in frame.columns:
        return set()
    keys: set[str] = set()
    for _, row in frame.iterrows():
        if not is_pulled(row.get("verlegt")):
            continue
        key = _norm_kabelnr(row.get("Kabelnr"))
        if key:
            keys.add(key)
    return keys


def status() -> dict:
    path = _meta_path()
    if path.exists():
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(meta, dict):
                return {
                    "loaded": bool(meta.get("loaded") and _parquet_path().exists()),
                    "file_name": meta.get("file_name") or "",
                    "cable_count": int(meta.get("cable_count") or 0),
                    "verlegt_count": int(meta.get("verlegt_count") or 0),
                    "uploaded_at": meta.get("uploaded_at"),
                }
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    if _parquet_path().exists():
        keys = load_live_verlegt_keys()
        frame = load_live_frame()
        return {
            "loaded": True,
            "file_name": _UPLOAD_NAME,
            "cable_count": int(len(frame)) if frame is not None else 0,
            "verlegt_count": len(keys),
            "uploaded_at": None,
        }
    return {
        "loaded": False,
        "file_name": "",
        "cable_count": 0,
        "verlegt_count": 0,
        "uploaded_at": None,
    }


def exclude_live_verlegt(df: pd.DataFrame, *, enabled: bool) -> tuple[pd.DataFrame, bool]:
    """Drop rows whose Kabelnr is verlegt in the live overlay.

    Returns (filtered_df, overlay_missing).
    When enabled but overlay missing, returns df unchanged and missing=True.
    """
    if df is None:
        return pd.DataFrame(), False
    if df.empty or not enabled:
        return df.copy(), False
    if not _parquet_path().exists():
        return df.copy(), True
    keys = load_live_verlegt_keys()
    if not keys or "Kabelnr" not in df.columns:
        return df.copy(), False
    norms = df["Kabelnr"].map(_norm_kabelnr)
    return df.loc[~norms.isin(keys)].copy(), False


def live_fully_pulled_m(joined: pd.DataFrame | None) -> float:
    """Sum Length_m (from joined dataset) for cables that already have verlegt in the live list."""
    if joined is None or joined.empty or "Length_m" not in joined.columns or "Kabelnr" not in joined.columns:
        return 0.0
    keys = load_live_verlegt_keys()
    if not keys:
        return 0.0
    norms = joined["Kabelnr"].map(_norm_kabelnr)
    lengths = pd.to_numeric(joined.loc[norms.isin(keys), "Length_m"], errors="coerce").fillna(0)
    return float(lengths.sum())
