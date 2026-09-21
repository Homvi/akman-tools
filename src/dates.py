from __future__ import annotations

from datetime import date, datetime

import pandas as pd

_FALSEY = {"", "false", "nein", "n", "0", "none", "-", "nan", "nat"}
_DATE_FORMATS = (
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d.%m.%y",
    "%d-%m-%Y",
    "%d/%m/%y",
    "%Y/%m/%d",
    "%d-%m-%y",
)


def parse_flexible_date(value) -> pd.Timestamp | pd.NaT:
    """Parse Excel dates, serials, and mistaken text dates."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return pd.NaT
    if isinstance(value, pd.Timestamp):
        return value if not pd.isna(value) and _plausible_year(value) else pd.NaT
    if isinstance(value, datetime):
        parsed = pd.Timestamp(value)
        return parsed if _plausible_year(parsed) else pd.NaT
    if isinstance(value, date):
        parsed = pd.Timestamp(value)
        return parsed if _plausible_year(parsed) else pd.NaT

    if isinstance(value, bool):
        return pd.NaT

    if isinstance(value, (int, float)) and not pd.isna(value):
        if value <= 0:
            return pd.NaT
        if value > 20000:
            parsed = pd.Timestamp("1899-12-30") + pd.to_timedelta(float(value), unit="D")
            return parsed if _plausible_year(parsed) else pd.NaT
        return pd.NaT

    text = str(value).strip()
    if text.lower() in _FALSEY:
        return pd.NaT

    if text.replace(".", "", 1).isdigit() or text.replace(",", "", 1).isdigit():
        try:
            serial = float(text.replace(",", "."))
            if serial > 20000:
                parsed = pd.Timestamp("1899-12-30") + pd.to_timedelta(serial, unit="D")
                if _plausible_year(parsed):
                    return parsed
        except ValueError:
            pass

    for fmt in _DATE_FORMATS:
        try:
            parsed = pd.Timestamp(datetime.strptime(text, fmt))
            return parsed if _plausible_year(parsed) else pd.NaT
        except ValueError:
            continue

    parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    if pd.isna(parsed) or not _plausible_year(parsed):
        return pd.NaT
    return pd.Timestamp(parsed)


def _plausible_year(value) -> bool:
    try:
        year = int(pd.Timestamp(value).year)
    except Exception:
        return False
    return 1990 <= year <= 2100


def series_to_dates(series: pd.Series) -> pd.Series:
    return series.map(parse_flexible_date)


def is_pulled(verlegt) -> bool:
    return pd.notna(parse_flexible_date(verlegt))
