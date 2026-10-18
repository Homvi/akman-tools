from __future__ import annotations

import math

import pandas as pd

from apps.api.services.jsonutil import records as json_records
from src.analysis import apply_filters, unique_devices
from src.pathways import unique_stop_stuetzen


def parse_list_param(value: str | None) -> list[str] | None:
    if not value:
        return None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts or None


def filter_cables(
    df: pd.DataFrame,
    *,
    devices: str | None = None,
    pulled: str | None = None,
    thickness: str | None = None,
    categories: str | None = None,
) -> pd.DataFrame:
    return apply_filters(
        df,
        devices=parse_list_param(devices),
        pulled=parse_list_param(pulled),
        thickness=parse_list_param(thickness),
        categories=parse_list_param(categories),
    )


def filter_options(df: pd.DataFrame) -> dict:
    cats = sorted(df["Category"].dropna().astype(str).unique().tolist()) if "Category" in df.columns else []
    thick = sorted(df["Thickness"].dropna().astype(str).unique().tolist()) if "Thickness" in df.columns else []
    return {
        "devices": unique_devices(df),
        "thickness": thick,
        "categories": cats,
        "stop_stuetzen": unique_stop_stuetzen(df) if not df.empty else [],
        "pull_statuses": ["Not pulled", "Részlegesen", "Pulled"],
    }


def paginate(df: pd.DataFrame, *, page: int = 1, page_size: int = 100) -> dict:
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 100), 1), 500)
    total = len(df)
    pages = max(int(math.ceil(total / page_size)), 1) if total else 1
    start = (page - 1) * page_size
    chunk = df.iloc[start : start + page_size]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "rows": json_records(chunk),
    }
