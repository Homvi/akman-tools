from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from src.progress import (
    KIND_COMPLETE,
    KIND_OPTIONS,
    KIND_PARTIAL,
    SLIDER_MAX,
    SLIDER_MIN,
    build_pull_events,
    daily_progress,
    progress_stats,
    weekly_hours,
    weekly_progress,
)
from src.store import load_workforce
from src.ui import download_button, filtered_frame, render_filters
from src.workforce import daily_hours


def _workforce_frame():
    if st.session_state.get("workforce") is not None:
        return st.session_state["workforce"]
    stored = load_workforce()
    if stored is None:
        return None
    st.session_state["workforce"] = stored["frame"]
    st.session_state["workforce_name"] = stored["file_name"]
    st.session_state["workforce_signature"] = stored["signature"]
    st.session_state["workforce_year"] = stored["year"]
    st.session_state["workforce_saved_at"] = stored.get("saved_at")
    return stored["frame"]


def _format_week_label(meters: float, hours: float | None) -> str:
    meters_txt = f"{meters:,.0f}" if abs(meters - round(meters)) < 0.05 else f"{meters:,.1f}"
    if hours is None or pd.isna(hours):
        return meters_txt
    hours_val = float(hours)
    hours_txt = f"{hours_val:,.0f}" if abs(hours_val - round(hours_val)) < 0.05 else f"{hours_val:,.1f}"
    return f"{meters_txt} ({hours_txt}h)"


def render() -> None:
    df = st.session_state.get("joined")
    if df is None:
        st.title("Pull progress")
        st.info("Upload both Excel files in the sidebar.")
        return

    render_filters(df)
    view = filtered_frame(df)
    events = build_pull_events(view)

    st.title("Pull progress")
    st.caption(
        "Daily pulled meters: partial pulls from Gestoppt dates, "
        "and the remaining length on the verlegt day as a complete pull."
    )

    if events.empty:
        st.info("No dated pulls for the current filters.")
        return

    kinds = st.multiselect(
        "Show",
        list(KIND_OPTIONS),
        default=list(KIND_OPTIONS),
        help="Partial and complete separately or together. Empty = both.",
    )
    if not kinds:
        kinds = list(KIND_OPTIONS)

    visible_events = events[events["Kind"].isin(kinds)]
    daily = daily_progress(visible_events, kinds)
    if visible_events.empty or daily.empty or daily["Date"].isna().all():
        st.info("No dated pulls for the current filters.")
        return

    min_day = max(pd.Timestamp(daily["Date"].min()).date(), SLIDER_MIN)
    max_day = min(pd.Timestamp(daily["Date"].max()).date(), SLIDER_MAX)
    if min_day > max_day:
        st.info("No displayable dates for the slider.")
        return
    if min_day == max_day:
        start, end = min_day, max_day
    else:
        start, end = st.slider(
            "Date range",
            min_value=min_day,
            max_value=max_day,
            value=(min_day, max_day),
            format="YYYY-MM-DD",
        )
    mask = (daily["Date"] >= pd.Timestamp(start)) & (daily["Date"] <= pd.Timestamp(end))
    daily_view = daily.loc[mask].copy()
    events_view = visible_events[
        (visible_events["Date"] >= pd.Timestamp(start)) & (visible_events["Date"] <= pd.Timestamp(end))
    ]
    stats = progress_stats(events_view, daily_view)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total pulled", f"{stats['total_m']:,.1f} m")
    m2.metric("Average speed", f"{stats['avg_m_per_day']:,.1f} m/day")
    m3.metric("Last 7 days avg", f"{stats['avg_last7']:,.1f} m/day")
    m4.metric(
        "Best day",
        f"{stats['best_day'].strftime('%Y-%m-%d') if stats['best_day'] is not None else '—'}",
        f"{stats['best_day_m']:,.1f} m",
    )

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Partial", f"{stats['partial_m']:,.1f} m")
    s2.metric("Complete", f"{stats['complete_m']:,.1f} m")
    s3.metric("Avg / pull", f"{stats['avg_event_m']:,.1f} m")
    s4.metric("Pull count", f"{stats['events']:,}")

    colors = {KIND_PARTIAL: "#f4a261", KIND_COMPLETE: "#2a9d8f"}
    long = daily_view.melt(
        id_vars=["Date"],
        value_vars=[kind for kind in kinds if kind in daily_view.columns],
        var_name="Kind",
        value_name="Meters",
    )

    st.subheader("Daily pulled meters")
    bar = (
        alt.Chart(long)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y("Meters:Q", title="Meters", stack="zero"),
            color=alt.Color(
                "Kind:N",
                title="Type",
                scale=alt.Scale(domain=list(kinds), range=[colors[k] for k in kinds]),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip("Date:T", title="Date", format="%Y-%m-%d"),
                alt.Tooltip("Kind:N", title="Type"),
                alt.Tooltip("Meters:Q", title="m", format=",.1f"),
            ],
        )
        .properties(height=320)
    )
    st.altair_chart(bar, use_container_width=True)

    weekly = weekly_progress(daily_view)
    st.subheader("Weekly pulled meters")
    st.caption("ISO week (KW), Monday to Sunday. Example: KW37 2026. Labels show total m and work hours when workforce data is loaded.")
    if not weekly.empty:
        weekly_long = weekly.melt(
            id_vars=["KW", "Year", "Week"],
            value_vars=[kind for kind in kinds if kind in weekly.columns],
            var_name="Kind",
            value_name="Meters",
        )
        week_order = weekly.sort_values(["Year", "Week"])["KW"].tolist()
        labels = weekly[["KW", "Total"]].copy()
        labels["Hours"] = pd.NA
        wf = _workforce_frame()
        if wf is not None and not wf.empty:
            hrs_daily = daily_hours(
                wf,
                exclude_weekends=False,
                trim_empty_tail=True,
                only_days_with_hours=True,
            )
            if not hrs_daily.empty:
                hrs_daily = hrs_daily.loc[
                    (pd.to_datetime(hrs_daily["Date"]) >= pd.Timestamp(start))
                    & (pd.to_datetime(hrs_daily["Date"]) <= pd.Timestamp(end))
                ]
            week_hrs = weekly_hours(hrs_daily)
            if not week_hrs.empty:
                labels = labels.drop(columns=["Hours"]).merge(week_hrs[["KW", "Hours"]], on="KW", how="left")
        labels["Label"] = [
            _format_week_label(float(m), None if pd.isna(h) else float(h))
            for m, h in zip(labels["Total"], labels["Hours"])
        ]
        week_bar = (
            alt.Chart(weekly_long)
            .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
            .encode(
                x=alt.X("KW:N", title="Week", sort=week_order),
                y=alt.Y("Meters:Q", title="Meters", stack="zero"),
                color=alt.Color(
                    "Kind:N",
                    title="Type",
                    scale=alt.Scale(domain=list(kinds), range=[colors[k] for k in kinds]),
                    legend=alt.Legend(orient="top"),
                ),
                tooltip=[
                    alt.Tooltip("KW:N", title="Week"),
                    alt.Tooltip("Kind:N", title="Type"),
                    alt.Tooltip("Meters:Q", title="m", format=",.1f"),
                ],
            )
        )
        week_labels = (
            alt.Chart(labels)
            .mark_text(dy=-10, fontSize=11, fontWeight="bold", color="#264653")
            .encode(
                x=alt.X("KW:N", sort=week_order),
                y=alt.Y("Total:Q"),
                text="Label:N",
                tooltip=[
                    alt.Tooltip("KW:N", title="Week"),
                    alt.Tooltip("Total:Q", title="Total m", format=",.1f"),
                    alt.Tooltip("Hours:Q", title="Work hours", format=",.1f"),
                ],
            )
        )
        st.altair_chart((week_bar + week_labels).properties(height=340), use_container_width=True)
        week_table = weekly.rename(
            columns={
                KIND_PARTIAL: "Partial_m",
                KIND_COMPLETE: "Complete_m",
                "Total": "Total_m",
                "Cumulative": "Cumulative_m",
            }
        )
        if "Hours" in labels.columns and labels["Hours"].notna().any():
            week_table = week_table.merge(labels[["KW", "Hours"]], on="KW", how="left")
            week_table = week_table.rename(columns={"Hours": "Work_hours"})
        st.dataframe(week_table, use_container_width=True, hide_index=True)
        download_button(week_table, "Export weekly progress", "pull_progress_weekly.xlsx")

    st.subheader("Cumulative length")
    cumul = (
        alt.Chart(daily_view)
        .mark_area(opacity=0.18, color="#264653")
        .encode(x=alt.X("Date:T", title="Date"), y=alt.Y("Cumulative:Q", title="Cumulative m"))
        + alt.Chart(daily_view)
        .mark_line(strokeWidth=2.5, color="#264653")
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y("Cumulative:Q", title="Cumulative m"),
            tooltip=[
                alt.Tooltip("Date:T", title="Date", format="%Y-%m-%d"),
                alt.Tooltip("Cumulative:Q", title="Cumulative m", format=",.1f"),
            ],
        )
    )
    st.altair_chart(cumul.properties(height=260), use_container_width=True)

    st.subheader("7-day average")
    rolling = (
        alt.Chart(daily_view)
        .mark_area(opacity=0.15, color="#e76f51")
        .encode(x=alt.X("Date:T", title="Date"), y=alt.Y("Rolling7:Q", title="m/day"))
        + alt.Chart(daily_view)
        .mark_line(strokeWidth=2.5, color="#e76f51")
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y("Rolling7:Q", title="m/day"),
            tooltip=[
                alt.Tooltip("Date:T", title="Date", format="%Y-%m-%d"),
                alt.Tooltip("Rolling7:Q", title="7-day average", format=",.1f"),
            ],
        )
    )
    st.altair_chart(rolling.properties(height=260), use_container_width=True)

    st.subheader("Daily data")
    table = daily_view.rename(
        columns={
            KIND_PARTIAL: "Partial_m",
            KIND_COMPLETE: "Complete_m",
            "Total": "Total_m",
            "Cumulative": "Cumulative_m",
            "Rolling7": "Avg_7day_m",
        }
    )
    st.dataframe(table, use_container_width=True, hide_index=True)
    download_button(table, "Export daily progress", "pull_progress.xlsx")
