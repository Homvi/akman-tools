from __future__ import annotations

import math
from typing import Any

import pandas as pd


def sanitize(value: Any) -> Any:
    """Make a value JSON-serializable (NaN/Inf/NaT → None)."""
    if value is None:
        return None
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return None if value in {"NaT", "NaN", "nan", "None"} else value
    if isinstance(value, (bytes, bytearray)):
        return None
    # pandas NaT / NA
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "isoformat") and not isinstance(value, str):
        try:
            out = value.isoformat()
            return None if out in {"NaT", "NaN"} else out
        except Exception:
            return str(value)
    if hasattr(value, "item") and not isinstance(value, (str, bytes, bytearray)):
        try:
            return sanitize(value.item())
        except Exception:
            return str(value)
    return value


def sanitize_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: sanitize_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_obj(v) for v in obj]
    return sanitize(obj)


def records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    out = df.where(pd.notna(df), None).to_dict(orient="records")
    return [sanitize_obj(row) for row in out]


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default
