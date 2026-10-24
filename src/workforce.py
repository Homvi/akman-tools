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


_POSITION_HEADERS = {"position", "skill", "profesion", "profession"}
_ABSENT_TOKENS = {
    "h",
    "holiday",
    "sick",
    "x",
    "u",
    "-",
    "—",
    "n/a",
    "na",
    "off",
}

# Cell mark for staffing UI (leave hints). Values stored in Status column.
_LEAVE_TOKENS = {
    "h",
    "holiday",
    "holidays",
    "urlaub",
    "szabadsag",
    "szabadság",
    "u",
    "sz",
    "leave",
    "vacation",
    "pto",
}
_SICK_TOKENS = {"sick", "beteg", "krank", "b", "s"}


def _is_position_header(cell: str) -> bool:
    key = cell.strip().lower()
    return key in _POSITION_HEADERS or key.startswith("position")


def _find_header_row(raw: pd.DataFrame) -> int | None:
    for i in range(min(12, len(raw))):
        cells = [_norm_text(v).lower() for v in raw.iloc[i].tolist()]
        if "name" in cells and any(_is_position_header(c) for c in cells if c):
            return i
    return None


def cell_status(value) -> str:
    """Classify a day cell: work | leave | sick | off | empty."""
    if value is None or isinstance(value, bool):
        return "empty"
    try:
        if pd.isna(value):
            return "empty"
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        text = value.replace("\xa0", " ").strip()
        if not text:
            return "empty"
        lower = text.lower()
        upper = text.upper()
        if lower in _LEAVE_TOKENS or "HOLIDAY" in upper or "URLAUB" in upper or "SZABADS" in upper:
            return "leave"
        if lower in _SICK_TOKENS or "SICK" in upper or "KRANK" in upper:
            return "sick"
        if lower in _ABSENT_TOKENS or upper in {"H"}:
            # H alone is leave (holiday); already caught above. Remaining tokens → off.
            if upper == "H" or lower in {"h", "holiday"}:
                return "leave"
            return "off"
        text_num = text.replace(",", ".")
        try:
            return "work" if float(text_num) > 0 else "off"
        except ValueError:
            return "off"
    try:
        return "work" if float(value) > 0 else "off"
    except (TypeError, ValueError):
        return "off"


def is_present(value) -> bool:
    """Numeric hours > 0 count as present. H / holiday / empty / 0 = not present."""
    return cell_status(value) == "work"


def _is_person_row(name: str, position: str) -> bool:
    if not name or _SKIP_NAME.match(name):
        return False
    pos = position.strip()
    if pos.lower() in _SKIP_POSITION:
        return False
    if "fitter" in name.lower() or "fitter" in pos.lower():
        return False
    return True


def _as_date(value) -> date | None:
    """Parse header cell into a calendar date (full datetime or day-of-month helper)."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.date()
    text = _norm_text(value)
    if not text or text.lower().startswith("total") or text.lower() in {"gesamt", "id"}:
        return None
    # Full date strings: 2026-06-10 / 10.06.2026
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    try:
        ts = pd.to_datetime(text, dayfirst=True, errors="coerce")
        if pd.notna(ts):
            return pd.Timestamp(ts).date()
    except (TypeError, ValueError):
        pass
    return None


def _is_day_number(value) -> bool:
    """True for plain day-of-month cells (1..31), not full dates."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return False
    if isinstance(value, (int, float)):
        try:
            if pd.isna(value):
                return False
        except (TypeError, ValueError):
            return False
        return float(value).is_integer() and 1 <= int(value) <= 31
    text = _norm_text(value)
    if not text or text.lower().startswith("total") or text.lower() in {"gesamt"}:
        return False
    try:
        num = float(text.replace(",", "."))
    except ValueError:
        return False
    return num.is_integer() and 1 <= int(num) <= 31


def _date_columns(header: pd.Series, *, year: int, month: int) -> list[tuple[int, date]]:
    """Return list of (column_index, calendar date).

    Supports:
    - day-of-month integers (legacy sheets)
    - full date / datetime headers (Arbeitsstunden Vorlage)
    """
    out: list[tuple[int, date]] = []
    for col, value in enumerate(header.tolist()):
        if _is_day_number(value):
            day = int(float(str(value).replace(",", ".")))
            try:
                out.append((col, date(year, month, day)))
            except ValueError:
                continue
            continue
        full = _as_date(value)
        if full is not None:
            out.append((col, full))
    return out


def _header_col(header: pd.Series, *names: str, default: int) -> int:
    """Find column by header label; earlier *names win (e.g. Position before Profesion)."""
    cells = [_norm_text(v).lower() for v in header.tolist()]
    for name in names:
        key = name.lower()
        for i, cell in enumerate(cells):
            if cell == key:
                return i
    for name in names:
        key = name.lower()
        for i, cell in enumerate(cells):
            if cell.startswith(key):
                return i
    return default


_EMPTY_COLS = ["Date", "Name", "Position", "Present", "Hours", "Status", "Sheet", "Project"]


def parse_workforce_sheet(
    raw: pd.DataFrame,
    sheet_name: str,
    *,
    year: int,
    project: str | None = None,
) -> pd.DataFrame:
    header_row = _find_header_row(raw)
    if header_row is None:
        return pd.DataFrame(columns=_EMPTY_COLS)

    month = detect_month(raw, sheet_name) or date.today().month
    header = raw.iloc[header_row]
    date_cols = _date_columns(header, year=year, month=month)
    if not date_cols:
        return pd.DataFrame(columns=_EMPTY_COLS)

    name_col = _header_col(header, "name", default=1)
    pos_col = _header_col(header, "position", "skill", "profesion", "profession", default=2)
    proj = str(project).strip() if project else None
    if proj == "":
        proj = None

    rows: list[dict] = []
    for r in range(header_row + 1, len(raw)):
        name = _norm_text(raw.iat[r, name_col] if name_col < raw.shape[1] else None)
        position = _norm_text(raw.iat[r, pos_col] if pos_col < raw.shape[1] else None)
        if not _is_person_row(name, position):
            continue
        for col, when in date_cols:
            if col >= raw.shape[1]:
                continue
            cell = raw.iat[r, col]
            status = cell_status(cell)
            present = status == "work"
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
                    "Status": status,
                    "Sheet": sheet_name,
                    "Project": proj,
                }
            )
    return pd.DataFrame(rows)


def parse_workforce_excel(
    source,
    *,
    year: int | None = None,
    project: str | None = None,
) -> pd.DataFrame:
    """Parse all month sheets into a long presence table.

    ``project`` tags every row (e.g. ship ``600``); ``None`` = main roster.
    """
    year = int(year or date.today().year)
    xl = pd.ExcelFile(source)
    frames = []
    for sheet in xl.sheet_names:
        raw = pd.read_excel(source, sheet_name=sheet, header=None)
        part = parse_workforce_sheet(raw, sheet, year=year, project=project)
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
