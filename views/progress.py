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
    weekly_progress,
)
from src.ui import download_button, filtered_frame, render_filters


def render() -> None:
    df = st.session_state.get("joined")
    if df is None:
        st.title("Behúzási ütem")
        st.info("Töltsd fel mindkét Excel fájlt az oldalsávban.")
        return

    render_filters(df)
    view = filtered_frame(df)
    events = build_pull_events(view)

    st.title("Behúzási ütem")
    st.caption(
        "Napi behúzott méter: a részleges húzások a Gestoppt dátumokból, "
        "a teljes húzás a verlegt napon a még hiányzó hossz."
    )

    if events.empty:
        st.info("Nincs dátumos húzás a jelenlegi szűrők mellett.")
        return

    kinds = st.multiselect(
        "Mit mutassunk",
        list(KIND_OPTIONS),
        default=list(KIND_OPTIONS),
        help="Részleges és teljes külön vagy együtt. Üres = mindkettő.",
    )
    if not kinds:
        kinds = list(KIND_OPTIONS)

    visible_events = events[events["Kind"].isin(kinds)]
    daily = daily_progress(visible_events, kinds)
    if visible_events.empty or daily.empty or daily["Date"].isna().all():
        st.info("Nincs dátumos húzás a jelenlegi szűrők mellett.")
        return

    min_day = max(pd.Timestamp(daily["Date"].min()).date(), SLIDER_MIN)
    max_day = min(pd.Timestamp(daily["Date"].max()).date(), SLIDER_MAX)
    if min_day > max_day:
        st.info("Nincs megjeleníthető dátum a csúszkához.")
        return
    if min_day == max_day:
        start, end = min_day, max_day
    else:
        start, end = st.slider(
            "Időszak",
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
    m1.metric("Összes behúzott", f"{stats['total_m']:,.1f} m")
    m2.metric("Átlagsebesség", f"{stats['avg_m_per_day']:,.1f} m/nap")
    m3.metric("Utolsó 7 nap átlag", f"{stats['avg_last7']:,.1f} m/nap")
    m4.metric(
        "Legjobb nap",
        f"{stats['best_day'].strftime('%Y-%m-%d') if stats['best_day'] is not None else '—'}",
        f"{stats['best_day_m']:,.1f} m",
    )

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Részleges", f"{stats['partial_m']:,.1f} m")
    s2.metric("Teljes", f"{stats['complete_m']:,.1f} m")
    s3.metric("Átlag / húzás", f"{stats['avg_event_m']:,.1f} m")
    s4.metric("Húzások száma", f"{stats['events']:,}")

    colors = {KIND_PARTIAL: "#f4a261", KIND_COMPLETE: "#2a9d8f"}
    long = daily_view.melt(
        id_vars=["Date"],
        value_vars=[kind for kind in kinds if kind in daily_view.columns],
        var_name="Kind",
        value_name="Meters",
    )

    st.subheader("Napi behúzott méter")
    bar = (
        alt.Chart(long)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("Date:T", title="Dátum"),
            y=alt.Y("Meters:Q", title="Méters", stack="zero"),
            color=alt.Color(
                "Kind:N",
                title="Típus",
                scale=alt.Scale(domain=list(kinds), range=[colors[k] for k in kinds]),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip("Date:T", title="Dátum", format="%Y-%m-%d"),
                alt.Tooltip("Kind:N", title="Típus"),
                alt.Tooltip("Meters:Q", title="m", format=",.1f"),
            ],
        )
        .properties(height=320)
    )
    st.altair_chart(bar, use_container_width=True)

    weekly = weekly_progress(daily_view)
    st.subheader("Heti behúzott méter")
    st.caption("ISO-hét (KW), hétfőtől vasárnapig. Például KW37 2026.")
    if not weekly.empty:
        weekly_long = weekly.melt(
            id_vars=["KW", "Year", "Week"],
            value_vars=[kind for kind in kinds if kind in weekly.columns],
            var_name="Kind",
            value_name="Meters",
        )
        week_order = weekly.sort_values(["Year", "Week"])["KW"].tolist()
        week_bar = (
            alt.Chart(weekly_long)
            .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
            .encode(
                x=alt.X("KW:N", title="Hét", sort=week_order),
                y=alt.Y("Meters:Q", title="Méters", stack="zero"),
                color=alt.Color(
                    "Kind:N",
                    title="Típus",
                    scale=alt.Scale(domain=list(kinds), range=[colors[k] for k in kinds]),
                    legend=alt.Legend(orient="top"),
                ),
                tooltip=[
                    alt.Tooltip("KW:N", title="Hét"),
                    alt.Tooltip("Kind:N", title="Típus"),
                    alt.Tooltip("Meters:Q", title="m", format=",.1f"),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(week_bar, use_container_width=True)
        week_table = weekly.rename(
            columns={
                KIND_PARTIAL: "Részleges_m",
                KIND_COMPLETE: "Teljes_m",
                "Total": "Összesen_m",
                "Cumulative": "Halmozott_m",
            }
        )
        st.dataframe(week_table, use_container_width=True, hide_index=True)
        download_button(week_table, "Heti ütem export", "behuzasi_utem_heti.xlsx")

    st.subheader("Halmozott hossz")
    cumul = (
        alt.Chart(daily_view)
        .mark_area(opacity=0.18, color="#264653")
        .encode(x=alt.X("Date:T", title="Dátum"), y=alt.Y("Cumulative:Q", title="Halmozott m"))
        + alt.Chart(daily_view)
        .mark_line(strokeWidth=2.5, color="#264653")
        .encode(
            x=alt.X("Date:T", title="Dátum"),
            y=alt.Y("Cumulative:Q", title="Halmozott m"),
            tooltip=[
                alt.Tooltip("Date:T", title="Dátum", format="%Y-%m-%d"),
                alt.Tooltip("Cumulative:Q", title="Halmozott m", format=",.1f"),
            ],
        )
    )
    st.altair_chart(cumul.properties(height=260), use_container_width=True)

    st.subheader("7 napos átlag")
    rolling = (
        alt.Chart(daily_view)
        .mark_area(opacity=0.15, color="#e76f51")
        .encode(x=alt.X("Date:T", title="Dátum"), y=alt.Y("Rolling7:Q", title="m/nap"))
        + alt.Chart(daily_view)
        .mark_line(strokeWidth=2.5, color="#e76f51")
        .encode(
            x=alt.X("Date:T", title="Dátum"),
            y=alt.Y("Rolling7:Q", title="m/nap"),
            tooltip=[
                alt.Tooltip("Date:T", title="Dátum", format="%Y-%m-%d"),
                alt.Tooltip("Rolling7:Q", title="7 napos átlag", format=",.1f"),
            ],
        )
    )
    st.altair_chart(rolling.properties(height=260), use_container_width=True)

    st.subheader("Napi adatok")
    table = daily_view.rename(
        columns={
            KIND_PARTIAL: "Részleges_m",
            KIND_COMPLETE: "Teljes_m",
            "Total": "Összesen_m",
            "Cumulative": "Halmozott_m",
            "Rolling7": "Atlag_7nap_m",
        }
    )
    st.dataframe(table, use_container_width=True, hide_index=True)
    download_button(table, "Napi ütem export", "behuzasi_utem.xlsx")
