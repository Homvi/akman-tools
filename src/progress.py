from __future__ import annotations

from datetime import date

import pandas as pd

KIND_PARTIAL = "Részleges"
KIND_COMPLETE = "Teljes"
KIND_OPTIONS = (KIND_PARTIAL, KIND_COMPLETE)
_EVENT_MIN = pd.Timestamp("1990-01-01")
_EVENT_MAX = pd.Timestamp("2100-12-31")
SLIDER_MIN = date(1685, 1, 1)
SLIDER_MAX = date(2254, 12, 31)


def _event_timestamp(value) -> pd.Timestamp | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    try:
        stamp = pd.Timestamp(value).normalize()
    except Exception:
        return None
    if pd.isna(stamp) or stamp < _EVENT_MIN or stamp > _EVENT_MAX:
        return None
    return stamp


def build_pull_events(df: pd.DataFrame) -> pd.DataFrame:
    """One row per pull: Gestoppt meters as partial, leftover length on verlegt as complete."""
    rows: list[dict] = []
    if df.empty:
        return _empty_events()

    for _, cable in df.iterrows():
        kabelnr = cable.get("Kabelnr")
        partial_sum = 0.0
        for slot in (1, 2, 3):
            stopped = cable.get(f"Gestoppt_{slot}")
            if pd.isna(stopped):
                continue
            meters = pd.to_numeric(cable.get(f"Teilgezogene_meter_{slot}"), errors="coerce")
            meters = 0.0 if pd.isna(meters) else float(meters)
            partial_sum += meters
            if meters <= 0:
                continue
            when = _event_timestamp(stopped)
            if when is None:
                continue
            rows.append(
                {
                    "Date": when,
                    "Meters": meters,
                    "Kind": KIND_PARTIAL,
                    "Kabelnr": kabelnr,
                }
            )

        when_done = _event_timestamp(cable.get("verlegt"))
        if when_done is None:
            continue
        length = pd.to_numeric(cable.get("Length_m"), errors="coerce")
        length = 0.0 if pd.isna(length) else float(length)
        remaining = max(length - partial_sum, 0.0)
        if remaining <= 0:
            continue
        rows.append(
            {
                "Date": when_done,
                "Meters": remaining,
                "Kind": KIND_COMPLETE,
                "Kabelnr": kabelnr,
            }
        )

    if not rows:
        return _empty_events()
    events = pd.DataFrame(rows)
    events = events.sort_values(["Date", "Kind", "Kabelnr"]).reset_index(drop=True)
    return events


def daily_progress(events: pd.DataFrame, kinds: list[str] | None = None) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame(columns=["Date", KIND_PARTIAL, KIND_COMPLETE, "Total", "Cumulative", "Rolling7"])
    selected = list(kinds) if kinds else list(KIND_OPTIONS)
    subset = events[events["Kind"].isin(selected)]
    if subset.empty:
        return pd.DataFrame(columns=["Date", KIND_PARTIAL, KIND_COMPLETE, "Total", "Cumulative", "Rolling7"])

    pivot = (
        subset.groupby(["Date", "Kind"], as_index=False)["Meters"]
        .sum()
        .pivot(index="Date", columns="Kind", values="Meters")
    )
    for kind in KIND_OPTIONS:
        if kind not in pivot.columns:
            pivot[kind] = 0.0
    pivot = pivot.fillna(0.0)
    full = pd.date_range(pivot.index.min(), pivot.index.max(), freq="D")
    pivot = pivot.reindex(full, fill_value=0.0)
    pivot.index.name = "Date"
    daily = pivot.reset_index()
    daily["Total"] = daily[KIND_PARTIAL] + daily[KIND_COMPLETE]
    daily["Cumulative"] = daily["Total"].cumsum()
    daily["Rolling7"] = daily["Total"].rolling(7, min_periods=1).mean()
    return daily


def weekly_progress(daily: pd.DataFrame) -> pd.DataFrame:
    empty = pd.DataFrame(
        columns=["Year", "Week", "KW", "Start", "End", KIND_PARTIAL, KIND_COMPLETE, "Total", "Cumulative"]
    )
    if daily.empty or "Date" not in daily.columns:
        return empty
    out = daily.copy()
    out["Date"] = pd.to_datetime(out["Date"])
    iso = out["Date"].dt.isocalendar()
    out["Year"] = iso.year.astype(int)
    out["Week"] = iso.week.astype(int)
    out["KW"] = ["KW" + f"{int(week):02d} {int(year)}" for year, week in zip(out["Year"], out["Week"])]
    for kind in KIND_OPTIONS:
        if kind not in out.columns:
            out[kind] = 0.0
    grouped = (
        out.groupby(["Year", "Week", "KW"], as_index=False)
        .agg(
            Start=("Date", "min"),
            End=("Date", "max"),
            **{
                KIND_PARTIAL: (KIND_PARTIAL, "sum"),
                KIND_COMPLETE: (KIND_COMPLETE, "sum"),
                "Total": ("Total", "sum"),
            },
        )
        .sort_values(["Year", "Week"])
        .reset_index(drop=True)
    )
    grouped["Cumulative"] = grouped["Total"].cumsum()
    return grouped


def progress_stats(events: pd.DataFrame, daily: pd.DataFrame) -> dict:
    if events.empty or daily.empty:
        return {
            "total_m": 0.0,
            "partial_m": 0.0,
            "complete_m": 0.0,
            "days": 0,
            "avg_m_per_day": 0.0,
            "avg_last7": 0.0,
            "avg_event_m": 0.0,
            "best_day": None,
            "best_day_m": 0.0,
            "events": 0,
        }
    total_m = float(events["Meters"].sum())
    partial_m = float(events.loc[events["Kind"].eq(KIND_PARTIAL), "Meters"].sum())
    complete_m = float(events.loc[events["Kind"].eq(KIND_COMPLETE), "Meters"].sum())
    days = int((daily["Date"].max() - daily["Date"].min()).days) + 1
    last7 = daily.tail(7)
    best_idx = daily["Total"].idxmax()
    best_row = daily.loc[best_idx]
    return {
        "total_m": total_m,
        "partial_m": partial_m,
        "complete_m": complete_m,
        "days": days,
        "avg_m_per_day": total_m / days if days else 0.0,
        "avg_last7": float(last7["Total"].mean()),
        "avg_event_m": float(events["Meters"].mean()),
        "best_day": pd.Timestamp(best_row["Date"]),
        "best_day_m": float(best_row["Total"]),
        "events": int(len(events)),
    }


def _empty_events() -> pd.DataFrame:
    return pd.DataFrame(columns=["Date", "Meters", "Kind", "Kabelnr"])
