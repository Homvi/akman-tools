from __future__ import annotations

from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from src.progress import build_pull_events, daily_progress
from src.store import clear_workforce
from src.ui import download_button
from src.workforce import (
    daily_headcount,
    daily_hours,
    headcount_growth,
    latest_headcount_day,
    meters_per_hour,
    meters_per_person,
    people_present_on,
    unique_positions,
)

_POSITION_COLORS = {
    "Cable puller": "#0d9488",
    "Electrician": "#d97706",
    "Office": "#1e3a5f",
    "Team lead": "#e11d48",
}


def _ensure_loaded() -> None:
    if "workforce" in st.session_state and st.session_state["workforce"] is not None:
        return
    from src.store import load_workforce

    stored = load_workforce()
    if stored is not None:
        st.session_state["workforce"] = stored["frame"]
        st.session_state["workforce_name"] = stored["file_name"]
        st.session_state["workforce_signature"] = stored["signature"]
        st.session_state["workforce_year"] = stored["year"]
        st.session_state["workforce_saved_at"] = stored.get("saved_at")


def _y_domain(data: pd.DataFrame) -> list[float]:
    y_max = float(data["Total"].max()) if not data.empty else 1.0
    return [0, max(y_max * 1.22, 1.0)]


def _headcount_growth_chart(daily: pd.DataFrame, focus_day) -> alt.Chart:
    """Area + line from zero, with the headcount written on every day."""
    data = daily.copy()
    data["Date"] = pd.to_datetime(data["Date"])
    data = data.sort_values("Date").reset_index(drop=True)
    data["Rolling7"] = data["Total"].rolling(7, min_periods=1).mean()
    start_val = float(data["Total"].iloc[0]) if not data.empty else 0.0
    data["Delta"] = data["Total"] - start_val
    data["Day"] = data["Date"].dt.strftime("%b %d")
    data["HeadcountLabel"] = data["Total"].round().astype(int).astype(str)

    domain = _y_domain(data)
    n = len(data)
    font_size = 12 if n <= 18 else (10 if n <= 32 else 8)
    y_scale = alt.Scale(domain=domain, nice=False, zero=True)
    x = alt.X(
        "Day:N",
        title=None,
        sort=list(data["Day"]),
        axis=alt.Axis(labelAngle=-40, labelOverlap=False),
    )

    area = (
        alt.Chart(data)
        .mark_area(
            line={"color": "#0f766e", "strokeWidth": 3.5},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="#ccfbf1", offset=0),
                    alt.GradientStop(color="#14b8a6", offset=0.55),
                    alt.GradientStop(color="#0f766e", offset=1),
                ],
                x1=1,
                x2=1,
                y1=1,
                y2=0,
            ),
            opacity=0.9,
        )
        .encode(
            x=x,
            y=alt.Y("Total:Q", title="People on site", scale=y_scale),
            tooltip=[
                alt.Tooltip("Date:T", title="Day", format="%Y-%m-%d"),
                alt.Tooltip("Total:Q", title="Headcount", format=",.0f"),
                alt.Tooltip("Delta:Q", title="Δ vs start", format="+,.0f"),
            ],
        )
    )

    rolling = (
        alt.Chart(data)
        .mark_line(strokeWidth=2.5, color="#134e4a", strokeDash=[6, 4])
        .encode(
            x=x,
            y=alt.Y("Rolling7:Q", scale=y_scale),
            tooltip=[
                alt.Tooltip("Date:T", title="Day", format="%Y-%m-%d"),
                alt.Tooltip("Rolling7:Q", title="7-day average", format=",.1f"),
            ],
        )
    )

    points = (
        alt.Chart(data)
        .mark_circle(size=55, color="#0f766e", opacity=1)
        .encode(x=x, y=alt.Y("Total:Q", scale=y_scale))
    )
    labels = (
        alt.Chart(data)
        .mark_text(dy=-12, fontSize=font_size, fontWeight="bold", color="#134e4a")
        .encode(x=x, y=alt.Y("Total:Q", scale=y_scale), text="HeadcountLabel:N")
    )

    layers = [area, rolling, points, labels]

    if focus_day is not None:
        focus_label = pd.Timestamp(focus_day).strftime("%b %d")
        layers.append(
            alt.Chart(pd.DataFrame({"Day": [focus_label]}))
            .mark_rule(color="#e11d48", strokeWidth=2, strokeDash=[5, 4])
            .encode(x=alt.X("Day:N", sort=list(data["Day"])))
        )

    return (
        alt.layer(*layers)
        .properties(height=440)
        .configure_view(strokeWidth=0)
        .configure_axis(gridColor="#e2e8f0", domainColor="#94a3b8", labelColor="#475569", titleColor="#334155")
    )


def _delta_growth_chart(daily: pd.DataFrame) -> alt.Chart:
    """Growth relative to first day — inherently steeper narrative, still true."""
    data = daily.copy()
    data["Date"] = pd.to_datetime(data["Date"])
    data = data.sort_values("Date").reset_index(drop=True)
    start = float(data["Total"].iloc[0])
    data["Delta"] = data["Total"] - start
    y_min = float(data["Delta"].min())
    y_max = float(data["Delta"].max())
    pad = max(1.0, (y_max - y_min) * 0.15 if y_max != y_min else 2.0)
    domain = [y_min - pad, y_max + pad]

    area = (
        alt.Chart(data)
        .mark_area(
            line={"color": "#b45309", "strokeWidth": 3},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="#ffedd5", offset=0),
                    alt.GradientStop(color="#f97316", offset=1),
                ],
                x1=1,
                x2=1,
                y1=1,
                y2=0,
            ),
            opacity=0.85,
        )
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %d", labelAngle=-30, tickCount=8)),
            y=alt.Y(
                "Delta:Q",
                title=f"Δ people (start = {int(start)})",
                scale=alt.Scale(domain=domain, nice=False, zero=False),
            ),
            tooltip=[
                alt.Tooltip("Date:T", title="Day", format="%Y-%m-%d"),
                alt.Tooltip("Total:Q", title="Headcount", format=",.0f"),
                alt.Tooltip("Delta:Q", title="Δ vs start", format="+,.0f"),
            ],
        )
    )
    zero = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(color="#78716c", strokeDash=[4, 4])
        .encode(y="y:Q")
    )
    return (
        alt.layer(area, zero)
        .properties(height=260)
        .configure_view(strokeWidth=0)
        .configure_axis(gridColor="#e2e8f0", labelColor="#475569", titleColor="#334155")
    )


def _position_stack_chart(daily: pd.DataFrame, positions: list[str]) -> alt.Chart | None:
    pos_cols = [c for c in positions if c in daily.columns]
    if not pos_cols:
        return None
    long = daily.melt(
        id_vars=["Date"],
        value_vars=pos_cols,
        var_name="Position",
        value_name="Count",
    )
    long["Date"] = pd.to_datetime(long["Date"])
    color_range = [_POSITION_COLORS.get(p, "#64748b") for p in pos_cols]
    return (
        alt.Chart(long)
        .mark_area(opacity=0.85, line=True)
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %d", labelAngle=-30, tickCount=8)),
            y=alt.Y("Count:Q", title="People", stack="zero"),
            color=alt.Color(
                "Position:N",
                scale=alt.Scale(domain=pos_cols, range=color_range),
                legend=alt.Legend(orient="top", title=None),
            ),
            tooltip=[
                alt.Tooltip("Date:T", title="Day", format="%Y-%m-%d"),
                alt.Tooltip("Position:N", title="Position"),
                alt.Tooltip("Count:Q", title="People", format=",.0f"),
            ],
        )
        .properties(height=280)
        .configure_view(strokeWidth=0)
    )


def _productivity_chart(prod: pd.DataFrame) -> alt.Chart:
    data = prod.copy()
    data["Date"] = pd.to_datetime(data["Date"])

    bars = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2, color="#94a3b8", opacity=0.45)
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %d", labelAngle=-30, tickCount=8)),
            y=alt.Y("Meters:Q", title="Pulled m / day"),
            tooltip=[
                alt.Tooltip("Date:T", title="Day", format="%Y-%m-%d"),
                alt.Tooltip("Meters:Q", title="Meters", format=",.1f"),
                alt.Tooltip("Headcount:Q", title="Headcount", format=",.0f"),
            ],
        )
    )
    ratio = (
        alt.Chart(data)
        .mark_line(strokeWidth=3, color="#c2410c", point=alt.OverlayMarkDef(size=40, filled=True))
        .encode(
            x="Date:T",
            y=alt.Y("M_per_person:Q", title="m / person", axis=alt.Axis(titleColor="#c2410c")),
            tooltip=[
                alt.Tooltip("Date:T", title="Day", format="%Y-%m-%d"),
                alt.Tooltip("M_per_person:Q", title="m / person", format=",.1f"),
                alt.Tooltip("Rolling7_m_per_person:Q", title="7-day avg m/person", format=",.1f"),
            ],
        )
    )
    rolling = (
        alt.Chart(data)
        .mark_line(strokeWidth=2, color="#9a3412", strokeDash=[5, 3])
        .encode(x="Date:T", y=alt.Y("Rolling7_m_per_person:Q", title="m / person"))
    )
    return (
        alt.layer(bars, ratio, rolling)
        .resolve_scale(y="independent")
        .properties(height=360)
        .configure_view(strokeWidth=0)
    )


def _hours_productivity_charts(prod: pd.DataFrame) -> tuple[alt.Chart, alt.Chart]:
    """Line = m/hour; second chart = work hours + meters that day."""
    data = prod.copy()
    data["Date"] = pd.to_datetime(data["Date"])

    ratio = (
        alt.Chart(data)
        .mark_line(strokeWidth=3.5, color="#0f766e", point=alt.OverlayMarkDef(size=55, filled=True, color="#0f766e"))
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %d", labelAngle=-30, tickCount=8)),
            y=alt.Y("M_per_hour:Q", title="m / hour"),
            tooltip=[
                alt.Tooltip("Date:T", title="Day", format="%Y-%m-%d"),
                alt.Tooltip("M_per_hour:Q", title="m / hour", format=",.2f"),
                alt.Tooltip("Rolling7_m_per_hour:Q", title="7-day avg m/hour", format=",.2f"),
                alt.Tooltip("Hours:Q", title="Work hours", format=",.1f"),
                alt.Tooltip("Meters:Q", title="Meters", format=",.1f"),
            ],
        )
    )
    rolling = (
        alt.Chart(data)
        .mark_line(strokeWidth=2, color="#134e4a", strokeDash=[5, 3])
        .encode(x="Date:T", y="Rolling7_m_per_hour:Q")
    )
    line_chart = (
        alt.layer(ratio, rolling)
        .properties(height=320)
        .configure_view(strokeWidth=0)
        .configure_axis(gridColor="#e2e8f0", labelColor="#475569", titleColor="#334155")
    )

    hours = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2, color="#64748b", opacity=0.65)
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %d", labelAngle=-30, tickCount=8)),
            y=alt.Y("Hours:Q", title="Work hours", axis=alt.Axis(titleColor="#475569")),
            tooltip=[
                alt.Tooltip("Date:T", title="Day", format="%Y-%m-%d"),
                alt.Tooltip("Hours:Q", title="Work hours", format=",.1f"),
                alt.Tooltip("Meters:Q", title="Meters", format=",.1f"),
                alt.Tooltip("Headcount:Q", title="People", format=",.0f"),
            ],
        )
    )
    meters = (
        alt.Chart(data)
        .mark_line(strokeWidth=3, color="#c2410c", point=alt.OverlayMarkDef(size=45, filled=True, color="#c2410c"))
        .encode(
            x="Date:T",
            y=alt.Y("Meters:Q", title="Pulled m", axis=alt.Axis(titleColor="#c2410c")),
            tooltip=[
                alt.Tooltip("Date:T", title="Day", format="%Y-%m-%d"),
                alt.Tooltip("Meters:Q", title="Meters", format=",.1f"),
                alt.Tooltip("Hours:Q", title="Work hours", format=",.1f"),
            ],
        )
    )
    hours_meters_chart = (
        alt.layer(hours, meters)
        .resolve_scale(y="independent")
        .properties(height=300)
        .configure_view(strokeWidth=0)
        .configure_axis(gridColor="#e2e8f0", labelColor="#475569", titleColor="#334155")
    )
    return line_chart, hours_meters_chart


def render() -> None:
    _ensure_loaded()

    st.title("Workforce")
    st.caption(
        "Upload the workforce hours Excel in the sidebar (optional Data files). "
        "H = holiday (not counted). Pulled m/hour uses Progressliste + CaTra from the sidebar."
    )

    df = st.session_state.get("workforce")
    if df is None or df.empty:
        st.info("Upload the workforce Excel in the sidebar (August / September sheets).")
        return

    name = st.session_state.get("workforce_name") or "workforce.xlsx"
    saved = st.session_state.get("workforce_saved_at")
    year = st.session_state.get("workforce_year")
    st.caption(
        f"Current file: **{name}**"
        + (f" · year: {year}" if year else "")
        + (f" · saved: {saved}" if saved else "")
    )

    if st.button("Clear workforce data"):
        clear_workforce()
        for key in ("workforce", "workforce_name", "workforce_signature", "workforce_year", "workforce_saved_at"):
            st.session_state.pop(key, None)
        st.rerun()

    positions = unique_positions(df)
    st.subheader("Positions")
    selected: list[str] = []
    cols = st.columns(min(4, max(1, len(positions))))
    for i, pos in enumerate(positions):
        with cols[i % len(cols)]:
            default_on = pos in {"Cable puller", "Electrician", "Team lead", "Office"}
            if st.checkbox(pos, value=default_on, key=f"wf_pos_{pos}"):
                selected.append(pos)
    if not selected:
        st.warning("Select at least one position.")
        return

    exclude_weekends = st.checkbox(
        "Exclude weekends (Sat–Sun)",
        value=True,
        key="wf_exclude_weekends",
        help="Charts and tables show weekdays only.",
    )

    daily = daily_headcount(
        df,
        selected,
        exclude_weekends=exclude_weekends,
        trim_empty_tail=True,
        only_days_with_people=True,
    )
    if daily.empty:
        st.info("No day has anyone entered for the selected positions.")
        return

    daily = daily.copy()
    daily["Date"] = pd.to_datetime(daily["Date"])
    min_day = pd.Timestamp(daily["Date"].min()).date()
    max_day = pd.Timestamp(daily["Date"].max()).date()
    if min_day == max_day:
        range_start, range_end = min_day, max_day
        st.caption(f"Date range: **{min_day.isoformat()}** (single day)")
    else:
        range_start, range_end = st.slider(
            "Date range",
            min_value=min_day,
            max_value=max_day,
            value=(min_day, max_day),
            format="YYYY-MM-DD",
            key="wf_date_range",
            help="Charts and metrics use this range.",
        )

    mask = (daily["Date"] >= pd.Timestamp(range_start)) & (daily["Date"] <= pd.Timestamp(range_end))
    daily = daily.loc[mask].reset_index(drop=True)
    if daily.empty:
        st.info("No data in the selected date range.")
        return

    focus_day, focus_count = latest_headcount_day(daily)
    growth = headcount_growth(daily)
    today = date.today()
    is_today = focus_day is not None and pd.Timestamp(focus_day).date() == today

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "On site today" if is_today else "Last day in file",
        f"{focus_count} people",
        delta=f"{growth['delta']:+d} vs start" if growth["delta"] else None,
    )
    m2.metric("Date", focus_day.strftime("%Y-%m-%d") if focus_day is not None else "—")
    m3.metric("Start → now", f"{growth['start']} → {growth['end']} people")
    m4.metric(
        "Peak",
        f"{growth['peak']} people",
        growth["peak_day"].strftime("%Y-%m-%d") if growth["peak_day"] is not None else None,
    )

    if focus_day is not None:
        with st.expander("Who is on site that day", expanded=False):
            people = people_present_on(df, focus_day, selected)
            if people.empty:
                st.info("Nobody from the selected positions on that day.")
            else:
                by_pos = people.groupby("Position")["Name"].count().sort_values(ascending=False)
                st.write(" · ".join(f"**{pos}:** {n}" for pos, n in by_pos.items()))
                st.dataframe(people, use_container_width=True, hide_index=True)

    if set(selected) == set(positions):
        growth_title = "Headcount growth"
    else:
        growth_title = f"Headcount growth — {' || '.join(selected)}"
    st.subheader(growth_title)
    st.caption("Only days with at least one person entered. Y-axis starts at zero. Numbers on the line are that day’s headcount.")
    st.altair_chart(_headcount_growth_chart(daily, focus_day), use_container_width=True)

    with st.expander("Growth vs start (Δ people)", expanded=True):
        st.caption(
            "Same days, but the axis shows change relative to the first day’s headcount "
            "(e.g. +3 people). Still real data — only the reference changes."
        )
        st.altair_chart(_delta_growth_chart(daily), use_container_width=True)

    stack = _position_stack_chart(daily, selected)
    if stack is not None:
        st.subheader("Mix by position")
        st.caption("Stacked area: how daily headcount is built from the selected positions.")
        st.altair_chart(stack, use_container_width=True)

    st.subheader("Pulled meters / work hour")
    joined = st.session_state.get("joined")
    if joined is None:
        st.info("Upload Progressliste + CaTra in the sidebar to see m/hour and m/person.")
    else:
        denom = st.radio(
            "Workforce in the denominator",
            ["Selected positions", "Cable puller + Electrician only"],
            horizontal=True,
            key="wf_prod_denom",
            help="For pull productivity, field crew (pullers / electricians) is usually the right base.",
        )
        if denom.startswith("Cable"):
            field_pos = [p for p in ("Cable puller", "Electrician") if p in positions]
            prod_positions = field_pos or selected
        else:
            prod_positions = selected

        hours_for_prod = daily_hours(
            df,
            prod_positions,
            exclude_weekends=exclude_weekends,
            trim_empty_tail=True,
            only_days_with_hours=True,
        )
        head_for_prod = daily_headcount(
            df,
            prod_positions,
            exclude_weekends=exclude_weekends,
            trim_empty_tail=True,
            only_days_with_people=True,
        )

        events = build_pull_events(joined)
        meters_daily = daily_progress(events)
        prod_h = meters_per_hour(hours_for_prod, meters_daily)
        prod = meters_per_person(head_for_prod, meters_daily)

        def _clip_prod(frame: pd.DataFrame, *, people_or_hours: str) -> pd.DataFrame:
            if frame.empty:
                return frame
            out = frame.copy()
            if exclude_weekends:
                dow = pd.to_datetime(out["Date"]).dt.dayofweek
                out = out.loc[dow < 5].reset_index(drop=True)
            key = "Hours" if people_or_hours == "hours" else "Headcount"
            if not out.empty and (out[key] > 0).any():
                last = out.loc[out[key] > 0, "Date"].max()
                out = out.loc[out["Date"] <= last].reset_index(drop=True)
            if not out.empty:
                out = out.loc[
                    (pd.to_datetime(out["Date"]) >= pd.Timestamp(range_start))
                    & (pd.to_datetime(out["Date"]) <= pd.Timestamp(range_end))
                ].reset_index(drop=True)
            if out.empty:
                return out
            out["Cumulative_m"] = out["Meters"].cumsum()
            if people_or_hours == "hours":
                out["Rolling7_m_per_hour"] = out["M_per_hour"].rolling(7, min_periods=1).mean()
            else:
                out["Rolling7_m_per_person"] = out["M_per_person"].rolling(7, min_periods=1).mean()
            return out

        prod_h = _clip_prod(prod_h, people_or_hours="hours")
        prod = _clip_prod(prod, people_or_hours="people")

        if prod_h.empty or prod_h["Meters"].sum() <= 0:
            st.warning("No overlapping dates between work hours and pulled meters.")
        else:
            active_h = prod_h[prod_h["Hours"] > 0]
            avg_h = float(active_h["M_per_hour"].mean()) if not active_h.empty else 0.0
            best_h = active_h.loc[active_h["M_per_hour"].idxmax()] if not active_h.empty else None
            h1, h2, h3, h4 = st.columns(4)
            h1.metric("Avg m/hour", f"{avg_h:,.2f}")
            h2.metric("Total work hours", f"{float(prod_h['Hours'].sum()):,.0f} h")
            h3.metric("Total pulled (range)", f"{float(prod_h['Meters'].sum()):,.0f} m")
            if best_h is not None:
                h4.metric(
                    "Best day m/hour",
                    f"{float(best_h['M_per_hour']):,.2f}",
                    pd.Timestamp(best_h["Date"]).strftime("%Y-%m-%d"),
                )
            st.caption("Teal line = meters per work hour. Dashed = 7-day average.")
            line_chart, hours_meters_chart = _hours_productivity_charts(prod_h)
            st.altair_chart(line_chart, use_container_width=True)
            st.caption("Grey bars = total work hours that day. Orange line = meters pulled that day.")
            st.altair_chart(hours_meters_chart, use_container_width=True)
            show_h = prod_h.rename(
                columns={
                    "Date": "Day",
                    "Hours": "Work_hours",
                    "Headcount": "People",
                    "Meters": "Pulled_m",
                    "M_per_hour": "m_per_hour",
                    "Cumulative_m": "Cumulative_m",
                    "Rolling7_m_per_hour": "Avg_7day_m_per_hour",
                }
            )
            show_h["Day"] = pd.to_datetime(show_h["Day"]).dt.strftime("%Y-%m-%d")
            st.dataframe(show_h, use_container_width=True, hide_index=True)
            download_button(prod_h, "Export m/hour", "pulled_per_hour.xlsx")

        with st.expander("Pulled meters / person", expanded=False):
            if prod.empty or prod["Meters"].sum() <= 0:
                st.warning("No overlapping dates between headcount and pulled meters.")
            else:
                active = prod[prod["Headcount"] > 0]
                avg_ratio = float(active["M_per_person"].mean()) if not active.empty else 0.0
                best = active.loc[active["M_per_person"].idxmax()] if not active.empty else None
                p1, p2, p3 = st.columns(3)
                p1.metric("Avg m/person (daily)", f"{avg_ratio:,.1f}")
                p2.metric("Total pulled (range)", f"{float(prod['Meters'].sum()):,.0f} m")
                if best is not None:
                    p3.metric(
                        "Best day m/person",
                        f"{float(best['M_per_person']):,.1f}",
                        pd.Timestamp(best["Date"]).strftime("%Y-%m-%d"),
                    )
                st.caption(
                    "Grey bars = daily pulled meters. Orange line = m/person. "
                    "Dashed = 7-day average m/person."
                )
                st.altair_chart(_productivity_chart(prod), use_container_width=True)
                show = prod.rename(
                    columns={
                        "Date": "Day",
                        "Headcount": "Headcount",
                        "Meters": "Pulled_m",
                        "M_per_person": "m_per_person",
                        "Cumulative_m": "Cumulative_m",
                        "Rolling7_m_per_person": "Avg_7day_m_per_person",
                    }
                )
                show["Day"] = pd.to_datetime(show["Day"]).dt.strftime("%Y-%m-%d")
                st.dataframe(show, use_container_width=True, hide_index=True)
                download_button(prod, "Export m/person", "pulled_per_person.xlsx")

    table = daily.rename(columns={"Total": "Total", "Date": "Day"})
    table["Day"] = pd.to_datetime(table["Day"]).dt.strftime("%Y-%m-%d")
    st.subheader("Daily headcount table")
    st.dataframe(table, use_container_width=True, hide_index=True)
    download_button(daily, "Export daily headcount", "headcount_daily.xlsx")
