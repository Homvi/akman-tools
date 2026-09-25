from __future__ import annotations

import re
from datetime import date, datetime

import pandas as pd

_MONTHS = {
    "january": 1,
    "januar": 1,
    "január": 1,
    "february": 2,
    "februar": 2,
    "február": 2,
    "march": 3,
    "marcius": 3,
    "március": 3,
    "april": 4,
    "aprilis": 4,
    "április": 4,
    "may": 5,
    "maj": 5,
    "május": 5,
    "june": 6,
    "junius": 6,
    "június": 6,
    "july": 7,
    "julius": 7,
    "július": 7,
    "august": 8,
    "augusztus": 8,
    "september": 9,
    "szeptember": 9,
    "october": 10,
    "oktober": 10,
    "október": 10,
    "november": 11,
    "december": 12,
}

_SKIP_NAME = re.compile(
    r"^(sum|name|total|h\s*=|this label|viking\d*\s*-?\s*fitters?)$",
    re.IGNORECASE,
)
_SKIP_POSITION = {
    "",
    "position",
    "projekt",
    "viking598",
    "viking600",
}


def _norm_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _month_from_text(text: str) -> int | None:
    key = re.sub(r"[^a-zA-ZáéíóöőúüűÁÉÍÓÖŐÚÜŰ]", "", text).lower()
    # strip accents for lookup of common keys already without accents in map
    plain = (
        key.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ö", "o")
        .replace("ő", "o")
        .replace("ú", "u")
        .replace("ü", "u")
        .replace("ű", "u")
    )
    return _MONTHS.get(key) or _MONTHS.get(plain)


def detect_month(raw: pd.DataFrame, sheet_name: str) -> int | None:
    month = _month_from_text(sheet_name)
    if month:
        return month
    for value in raw.iloc[:6].to_numpy().ravel():
        text = _norm_text(value)
        if not text:
            continue
        found = _month_from_text(text)
        if found:
            return found
    return None


def _find_header_row(raw: pd.DataFrame) -> int | None:
    for i in range(min(12, len(raw))):
        cells = [_norm_text(v).lower() for v in raw.iloc[i].tolist()]
        if "name" in cells and any(c == "position" or c.startswith("position") for c in cells):
            return i
    return None


def is_present(value) -> bool:
    """Numeric hours > 0 count as present. H / holiday / empty / 0 = not present."""
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        upper = text.upper()
        if upper in {"H", "HOLIDAY"} or "HOLIDAY" in upper:
            return False
        text = text.replace(",", ".")
        try:
            return float(text) > 0
        except ValueError:
            return False
    if isinstance(value, (int, float)):
        return float(value) > 0
    return False


def _is_person_row(name: str, position: str) -> bool:
    if not name or _SKIP_NAME.match(name):
        return False
    pos = position.strip()
    if pos.lower() in _SKIP_POSITION:
        return False
    if "fitter" in name.lower() or "fitter" in pos.lower():
        return False
    return True


def _day_columns(header: pd.Series) -> list[tuple[int, int]]:
    """Return list of (column_index, day_of_month)."""
    out: list[tuple[int, int]] = []
    for col, value in enumerate(header.tolist()):
        text = _norm_text(value)
        if not text:
            continue
        if text.lower().startswith("total"):
            continue
        try:
            day = int(float(str(text).replace(",", ".")))
        except ValueError:
            continue
        if 1 <= day <= 31:
            out.append((col, day))
    return out


def parse_workforce_sheet(raw: pd.DataFrame, sheet_name: str, *, year: int) -> pd.DataFrame:
    header_row = _find_header_row(raw)
    if header_row is None:
        return pd.DataFrame(columns=["Date", "Name", "Position", "Present", "Hours", "Sheet"])

    month = detect_month(raw, sheet_name) or date.today().month
    header = raw.iloc[header_row]
    day_cols = _day_columns(header)
    if not day_cols:
        return pd.DataFrame(columns=["Date", "Name", "Position", "Present", "Hours", "Sheet"])

    name_col = next((i for i, v in enumerate(header.tolist()) if _norm_text(v).lower() == "name"), 1)
    pos_col = next((i for i, v in enumerate(header.tolist()) if _norm_text(v).lower() == "position"), 2)

    rows: list[dict] = []
    for r in range(header_row + 1, len(raw)):
        name = _norm_text(raw.iat[r, name_col] if name_col < raw.shape[1] else None)
        position = _norm_text(raw.iat[r, pos_col] if pos_col < raw.shape[1] else None)
        if not _is_person_row(name, position):
            continue
        for col, day in day_cols:
            if col >= raw.shape[1]:
                continue
            try:
                when = date(year, month, day)
            except ValueError:
                continue
            cell = raw.iat[r, col]
            present = is_present(cell)
            hours = None
            if present:
                try:
                    hours = float(str(cell).replace(",", "."))
                except (TypeError, ValueError):
                    hours = None
            rows.append(
                {
                    "Date": pd.Timestamp(when),
                    "Name": name,
                    "Position": position,
                    "Present": present,
                    "Hours": hours,
                    "Sheet": sheet_name,
                }
            )
    return pd.DataFrame(rows)


def parse_workforce_excel(source, *, year: int | None = None) -> pd.DataFrame:
    """Parse all month sheets into a long presence table."""
    year = int(year or date.today().year)
    xl = pd.ExcelFile(source)
    frames = []
    for sheet in xl.sheet_names:
        raw = pd.read_excel(source, sheet_name=sheet, header=None)
        part = parse_workforce_sheet(raw, sheet, year=year)
        if not part.empty:
            frames.append(part)
    if not frames:
        raise ValueError("No workforce rows found (Name / position / day columns).")
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["Date", "Position", "Name"]).reset_index(drop=True)
    return out


def unique_positions(df: pd.DataFrame) -> list[str]:
    if df is None or df.empty or "Position" not in df.columns:
        return []
    return sorted({str(p).strip() for p in df["Position"].dropna() if str(p).strip()})


def daily_headcount(
    df: pd.DataFrame,
    positions: list[str] | None = None,
    *,
    exclude_weekends: bool = False,
    trim_empty_tail: bool = True,
    only_days_with_people: bool = True,
) -> pd.DataFrame:
    """
    One row per date: Total + optional per-position counts of present people.

    - trim_empty_tail: stop at the last day where someone is still present
    - exclude_weekends: drop Saturday / Sunday
    - only_days_with_people: drop days where Total == 0 (no one entered)
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["Date", "Total"])

    base = df.copy()
    if positions:
        wanted = {p.strip() for p in positions}
        base = base[base["Position"].astype(str).str.strip().isin(wanted)]
    if base.empty:
        return pd.DataFrame(columns=["Date", "Total"])

    dates = pd.date_range(base["Date"].min(), base["Date"].max(), freq="D")
    view = base[base["Present"]].copy()

    total = (
        view.groupby("Date")["Name"].nunique().reindex(dates, fill_value=0).astype(int).rename("Total")
    )
    out = total.reset_index().rename(columns={"index": "Date"})
    if "Date" not in out.columns:
        out = total.rename_axis("Date").reset_index()

    if not view.empty:
        by_pos = (
            view.groupby(["Date", "Position"])["Name"]
            .nunique()
            .unstack(fill_value=0)
            .reindex(dates, fill_value=0)
            .astype(int)
        )
        by_pos = by_pos.reset_index().rename(columns={"index": "Date"})
        if "Date" not in by_pos.columns:
            by_pos = by_pos.rename_axis("Date").reset_index()
        out = out.merge(by_pos, on="Date", how="left")
        for col in out.columns:
            if col not in {"Date", "Total"}:
                out[col] = out[col].fillna(0).astype(int)

    out = out.sort_values("Date").reset_index(drop=True)

    if trim_empty_tail and not out.empty:
        present_mask = out["Total"] > 0
        if present_mask.any():
            last_idx = present_mask[::-1].idxmax()
            out = out.loc[:last_idx].copy()
        else:
            return out.iloc[0:0].copy()

    if exclude_weekends and not out.empty:
        dow = pd.to_datetime(out["Date"]).dt.dayofweek
        out = out.loc[dow < 5].reset_index(drop=True)

    if only_days_with_people and not out.empty:
        out = out.loc[out["Total"] > 0].reset_index(drop=True)

    return out.reset_index(drop=True)


def latest_headcount_day(daily: pd.DataFrame, *, as_of: date | None = None) -> tuple[pd.Timestamp | None, int]:
    """Prefer today if it has people; else last day with Total > 0."""
    if daily is None or daily.empty:
        return None, 0
    as_of = as_of or date.today()
    today_ts = pd.Timestamp(as_of)
    today_rows = daily.loc[daily["Date"].eq(today_ts) & daily["Total"].gt(0)]
    if not today_rows.empty:
        return today_ts, int(today_rows.iloc[0]["Total"])
    with_people = daily.loc[daily["Total"] > 0].sort_values("Date")
    if with_people.empty:
        return None, 0
    last = with_people.iloc[-1]
    return pd.Timestamp(last["Date"]), int(last["Total"])


def people_present_on(df: pd.DataFrame, day: pd.Timestamp | date, positions: list[str] | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["Name", "Position", "Hours"])
    day = pd.Timestamp(day).normalize()
    view = df[df["Present"] & df["Date"].eq(day)].copy()
    if positions:
        wanted = {p.strip() for p in positions}
        view = view[view["Position"].astype(str).str.strip().isin(wanted)]
    return view[["Name", "Position", "Hours"]].sort_values(["Position", "Name"]).reset_index(drop=True)


def headcount_growth(daily: pd.DataFrame) -> dict:
    """Summary of how headcount changed over the visible series."""
    if daily is None or daily.empty or "Total" not in daily.columns:
        return {"start": 0, "end": 0, "peak": 0, "peak_day": None, "delta": 0}
    series = daily.sort_values("Date")
    start = int(series["Total"].iloc[0])
    end = int(series["Total"].iloc[-1])
    peak_idx = series["Total"].idxmax()
    peak = int(series.loc[peak_idx, "Total"])
    peak_day = pd.Timestamp(series.loc[peak_idx, "Date"])
    return {"start": start, "end": end, "peak": peak, "peak_day": peak_day, "delta": end - start}


def daily_hours(
    df: pd.DataFrame,
    positions: list[str] | None = None,
    *,
    exclude_weekends: bool = False,
    trim_empty_tail: bool = True,
    only_days_with_hours: bool = True,
) -> pd.DataFrame:
    """
    One row per date: total work hours (sum of entered hours) and headcount.

    Uses the numeric cell values from the workforce sheet (e.g. 10, 9.5).
    """
    empty = pd.DataFrame(columns=["Date", "Hours", "Headcount"])
    if df is None or df.empty:
        return empty

    base = df.copy()
    if positions:
        wanted = {p.strip() for p in positions}
        base = base[base["Position"].astype(str).str.strip().isin(wanted)]
    if base.empty:
        return empty

    view = base[base["Present"]].copy()
    if view.empty:
        return empty

    view["Hours"] = pd.to_numeric(view["Hours"], errors="coerce").fillna(0.0)
    dates = pd.date_range(base["Date"].min(), base["Date"].max(), freq="D")
    hours = view.groupby("Date")["Hours"].sum().reindex(dates, fill_value=0.0).rename("Hours")
    people = view.groupby("Date")["Name"].nunique().reindex(dates, fill_value=0).astype(int).rename("Headcount")
    out = pd.concat([hours, people], axis=1).reset_index().rename(columns={"index": "Date"})
    if "Date" not in out.columns:
        out = pd.concat([hours, people], axis=1).rename_axis("Date").reset_index()
    out["Hours"] = pd.to_numeric(out["Hours"], errors="coerce").fillna(0.0)
    out["Headcount"] = out["Headcount"].fillna(0).astype(int)
    out = out.sort_values("Date").reset_index(drop=True)

    if trim_empty_tail and not out.empty:
        present_mask = out["Hours"] > 0
        if present_mask.any():
            last_idx = present_mask[::-1].idxmax()
            out = out.loc[:last_idx].copy()
        else:
            return out.iloc[0:0].copy()

    if exclude_weekends and not out.empty:
        dow = pd.to_datetime(out["Date"]).dt.dayofweek
        out = out.loc[dow < 5].reset_index(drop=True)

    if only_days_with_hours and not out.empty:
        out = out.loc[out["Hours"] > 0].reset_index(drop=True)

    return out.reset_index(drop=True)


def meters_per_hour(
    daily_hrs: pd.DataFrame,
    daily_meters: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join daily pulled meters with work hours.
    Returns Date, Hours, Headcount, Meters, M_per_hour, Cumulative_m, Rolling7_m_per_hour.
    """
    empty = pd.DataFrame(
        columns=[
            "Date",
            "Hours",
            "Headcount",
            "Meters",
            "M_per_hour",
            "Cumulative_m",
            "Rolling7_m_per_hour",
        ]
    )
    if daily_hrs is None or daily_hrs.empty or daily_meters is None or daily_meters.empty:
        return empty

    hrs = daily_hrs[["Date", "Hours"] + (["Headcount"] if "Headcount" in daily_hrs.columns else [])].copy()
    hrs["Date"] = pd.to_datetime(hrs["Date"]).dt.normalize()
    if "Headcount" not in hrs.columns:
        hrs["Headcount"] = 0

    meters = daily_meters[["Date", "Total"]].copy()
    meters["Date"] = pd.to_datetime(meters["Date"]).dt.normalize()
    meters = meters.rename(columns={"Total": "Meters"})

    start = max(hrs["Date"].min(), meters["Date"].min())
    end = min(hrs["Date"].max(), meters["Date"].max())
    if pd.isna(start) or pd.isna(end) or start > end:
        return empty

    days = pd.date_range(start, end, freq="D")
    out = pd.DataFrame({"Date": days})
    out = out.merge(hrs, on="Date", how="left").merge(meters, on="Date", how="left")
    out["Hours"] = pd.to_numeric(out["Hours"], errors="coerce").fillna(0.0)
    out["Headcount"] = out["Headcount"].fillna(0).astype(int)
    out["Meters"] = pd.to_numeric(out["Meters"], errors="coerce").fillna(0.0)
    out["M_per_hour"] = out.apply(
        lambda r: float(r["Meters"]) / float(r["Hours"]) if r["Hours"] > 0 else 0.0,
        axis=1,
    )
    out["Cumulative_m"] = out["Meters"].cumsum()
    out["Rolling7_m_per_hour"] = out["M_per_hour"].rolling(7, min_periods=1).mean()
    return out.reset_index(drop=True)


def meters_per_person(
    daily_head: pd.DataFrame,
    daily_meters: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join daily pulled meters with headcount.
    Returns Date, Headcount, Meters, M_per_person, Cumulative_m, Rolling7_m_per_person.
    """
    empty = pd.DataFrame(
        columns=[
            "Date",
            "Headcount",
            "Meters",
            "M_per_person",
            "Cumulative_m",
            "Rolling7_m_per_person",
        ]
    )
    if daily_head is None or daily_head.empty or daily_meters is None or daily_meters.empty:
        return empty

    head = daily_head[["Date", "Total"]].copy()
    head["Date"] = pd.to_datetime(head["Date"]).dt.normalize()
    head = head.rename(columns={"Total": "Headcount"})

    meters = daily_meters[["Date", "Total"]].copy()
    meters["Date"] = pd.to_datetime(meters["Date"]).dt.normalize()
    meters = meters.rename(columns={"Total": "Meters"})

    start = max(head["Date"].min(), meters["Date"].min())
    end = min(head["Date"].max(), meters["Date"].max())
    if pd.isna(start) or pd.isna(end) or start > end:
        return empty

    days = pd.date_range(start, end, freq="D")
    out = pd.DataFrame({"Date": days})
    out = out.merge(head, on="Date", how="left").merge(meters, on="Date", how="left")
    out["Headcount"] = out["Headcount"].fillna(0).astype(int)
    out["Meters"] = pd.to_numeric(out["Meters"], errors="coerce").fillna(0.0)
    out["M_per_person"] = out.apply(
        lambda r: float(r["Meters"]) / float(r["Headcount"]) if r["Headcount"] > 0 else 0.0,
        axis=1,
    )
    out["Cumulative_m"] = out["Meters"].cumsum()
    out["Rolling7_m_per_person"] = out["M_per_person"].rolling(7, min_periods=1).mean()
    return out.reset_index(drop=True)
