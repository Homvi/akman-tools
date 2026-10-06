from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.areas import (
    DEFAULT_HOURS_PER_WEEK,
    DEFAULT_H_PER_STUETZE,
    DEFAULT_MAX_PER_ROOM,
    DEFAULT_PULLERS,
    DEFAULT_THICK_PACE,
    DEFAULT_THIN_PACE,
    affected_areas,
    node_key,
    remaining_cables_frame,
    summarize_all_areas,
    totals_from_summaries,
)
from src.export import catra_list_xlsx, kurzliste_xlsx, safe_filename
from src.store import load_areas, load_areas_settings, save_areas_settings
from src.ui import cable_export_buttons, filtered_frame, render_filters, visible_columns


def _ensure_areas_loaded() -> list | None:
    if st.session_state.get("areas"):
        return st.session_state["areas"]
    stored = load_areas()
    if stored is None:
        return None
    st.session_state["areas"] = stored["areas"]
    st.session_state["areas_name"] = stored["file_name"]
    st.session_state["areas_signature"] = stored["signature"]
    st.session_state["areas_saved_at"] = stored.get("saved_at")
    return stored["areas"]


def _default_settings() -> dict:
    return {
        "thin_pace": DEFAULT_THIN_PACE,
        "thick_pace": DEFAULT_THICK_PACE,
        "h_per_stuetze": DEFAULT_H_PER_STUETZE,
        "pullers": DEFAULT_PULLERS,
        "hours_per_week": DEFAULT_HOURS_PER_WEEK,
        "max_per_room": DEFAULT_MAX_PER_ROOM,
        "priority": {},  # area_key -> int (lower = sooner)
        "installed": {},  # area_key -> list[str]
        "blocks": [],  # list of entity strings
    }


def _load_settings() -> dict:
    if "areas_settings" in st.session_state and st.session_state["areas_settings"] is not None:
        return st.session_state["areas_settings"]
    stored = load_areas_settings()
    settings = _default_settings()
    if stored:
        settings.update(stored)
    settings.setdefault("installed", {})
    settings.setdefault("blocks", [])
    settings.setdefault("priority", {})
    settings.setdefault("max_per_room", DEFAULT_MAX_PER_ROOM)
    st.session_state["areas_settings"] = settings
    return settings


def _persist_settings(settings: dict) -> None:
    st.session_state["areas_settings"] = settings
    try:
        save_areas_settings(settings)
    except Exception as exc:
        st.warning(f"Could not save area settings: {exc}")


def _planning_bar(settings: dict) -> dict:
    st.subheader("Planning")
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    thin = c1.number_input(
        "Thin m/h",
        min_value=0.1,
        value=float(settings.get("thin_pace") or DEFAULT_THIN_PACE),
        step=1.0,
        key="areas_thin_pace",
    )
    thick = c2.number_input(
        "Thick m/h",
        min_value=0.1,
        value=float(settings.get("thick_pace") or DEFAULT_THICK_PACE),
        step=0.5,
        key="areas_thick_pace",
    )
    h_st = c3.number_input(
        "Hours / Stütze",
        min_value=0.0,
        value=float(settings.get("h_per_stuetze") or DEFAULT_H_PER_STUETZE),
        step=0.5,
        key="areas_h_stuetze",
    )
    pullers = c4.number_input(
        "Cable pullers",
        min_value=1,
        value=int(settings.get("pullers") or DEFAULT_PULLERS),
        step=1,
        key="areas_pullers",
        help="Shared puller pool across rooms.",
    )
    max_room = c5.number_input(
        "Max pullers / room",
        min_value=1,
        value=int(settings.get("max_per_room") or DEFAULT_MAX_PER_ROOM),
        step=1,
        key="areas_max_per_room",
        help="Cap per room (default 5).",
    )
    hours_week = c6.number_input(
        "Hours / puller / week",
        min_value=1.0,
        value=float(settings.get("hours_per_week") or DEFAULT_HOURS_PER_WEEK),
        step=1.0,
        key="areas_hours_week",
    )
    as_of = c7.date_input(
        "As-of date",
        value=date.today(),
        key="areas_as_of",
    )
    changed = (
        thin != settings.get("thin_pace")
        or thick != settings.get("thick_pace")
        or h_st != settings.get("h_per_stuetze")
        or int(pullers) != int(settings.get("pullers") or 0)
        or int(max_room) != int(settings.get("max_per_room") or 0)
        or hours_week != settings.get("hours_per_week")
    )
    if changed:
        settings["thin_pace"] = float(thin)
        settings["thick_pace"] = float(thick)
        settings["h_per_stuetze"] = float(h_st)
        settings["pullers"] = int(pullers)
        settings["max_per_room"] = int(max_room)
        settings["hours_per_week"] = float(hours_week)
        _persist_settings(settings)
    return {
        "thin_pace": float(thin),
        "thick_pace": float(thick),
        "h_per_stuetze": float(h_st),
        "pullers": int(pullers),
        "max_per_room": int(max_room),
        "hours_per_week": float(hours_week),
        "as_of": as_of if isinstance(as_of, date) else date.today(),
    }


def _show_schedule_metrics(title: str, schedule: dict, person_hours: float, remaining_m: float) -> None:
    st.markdown(f"**{title}**")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Person-hours", f"{person_hours:,.1f}")
    m2.metric("Remaining m", f"{remaining_m:,.1f}")
    m3.metric("Workdays", f"{schedule['workdays']}")
    m4.metric("Ready date", schedule["end_date"].isoformat())
    m5.metric("Calendar week", schedule["kw"])


def _overview_table(summaries: list[dict], blocks: list[str], priority_map: dict) -> pd.DataFrame:
    blocked_areas = {b[5:] for b in blocks if b.startswith("area:")}
    rows = []
    for s in summaries:
        area = s["area"]
        sch = s["schedule"]
        start = sch.get("start_date")
        manual = priority_map.get(area.key)
        rows.append(
            {
                "Priority": int(manual) if manual is not None else "",
                "Area": area.name,
                "Deck": area.deck,
                "ID": area.area_ids,
                "Cables": s["cables"],
                "Thick": s["thick"],
                "Thin": s["thin"],
                "Through": s["through"],
                "Terminate": s["terminate"],
                "Stops": s["stop"],
                "Pulled %": round(s["pulled_pct"], 1),
                "Remaining m": round(s["remaining_m"], 1),
                "Person-hours": round(s["person_hours"], 1),
                "Crew": int(s.get("crew") or 0),
                "Start": start.isoformat() if start else "",
                "Workdays": sch["workdays"],
                "KW": sch["kw"],
                "Blocked": area.key in blocked_areas,
                "_key": area.key,
            }
        )
    return pd.DataFrame(rows)


def _from_zero_table(summaries: list[dict]) -> pd.DataFrame:
    rows = []
    for s in summaries:
        area = s["area"]
        rows.append(
            {
                "Area": area.name,
                "Deck": area.deck,
                "Through thick": s.get("thick_through", 0),
                "Through thin": s.get("thin_through", 0),
                "Terminate thick": s.get("thick_terminate", 0),
                "Terminate thin": s.get("thin_terminate", 0),
                "From-zero hours": round(float(s.get("zero_person_hours") or 0.0), 1),
                "Weeks (≤5/room)": round(float(s.get("zero_weeks") or 0.0), 2),
            }
        )
    return pd.DataFrame(rows)


def _priority_editor(summaries: list[dict], settings: dict) -> None:
    st.markdown("**Priority** (lower number = sooner; blank = auto by Pulled %)")
    priority = dict(settings.get("priority") or {})
    changed = False
    for s in summaries:
        area = s["area"]
        current = priority.get(area.key)
        col_a, col_b = st.columns([4, 1])
        col_a.caption(f"{area.name} · {area.deck}")
        new_val = col_b.number_input(
            "Prio",
            min_value=0,
            value=int(current) if current is not None else 0,
            step=1,
            key=f"prio_{area.key}",
            label_visibility="collapsed",
            help="0 = unset (auto). Positive ints set manual order.",
        )
        # Treat 0 as unset so auto-order works by default
        if new_val and int(new_val) > 0:
            if priority.get(area.key) != int(new_val):
                priority[area.key] = int(new_val)
                changed = True
        elif area.key in priority:
            del priority[area.key]
            changed = True
    if changed:
        settings["priority"] = priority
        _persist_settings(settings)
        st.rerun()


def _toggle_block(settings: dict, entity: str, enabled: bool) -> None:
    blocks = list(settings.get("blocks") or [])
    if enabled and entity not in blocks:
        blocks.append(entity)
    if not enabled and entity in blocks:
        blocks = [b for b in blocks if b != entity]
    settings["blocks"] = blocks
    _persist_settings(settings)


def _set_installed(settings: dict, area_key: str, stuetze: str, installed: bool) -> None:
    installed_map = dict(settings.get("installed") or {})
    current = list(installed_map.get(area_key) or [])
    keys = {node_key(x): x for x in current}
    k = node_key(stuetze)
    if installed:
        if k not in keys:
            current.append(stuetze)
    else:
        current = [x for x in current if node_key(x) != k]
    installed_map[area_key] = current
    settings["installed"] = installed_map
    _persist_settings(settings)


def _render_detail(
    summary: dict,
    areas: list,
    summaries: list[dict],
    df: pd.DataFrame,
    settings: dict,
    plan: dict,
) -> None:
    area = summary["area"]
    sch = summary["schedule"]
    st.subheader(f"{area.name} · {area.deck}")
    if area.area_ids:
        st.caption(f"Area ID: {area.area_ids}")
    crew = int(summary.get("crew") or 0)
    start = sch.get("start_date")
    st.caption(
        f"Crew {crew} · start {start.isoformat() if start else '—'} · "
        f"queue #{summary.get('queue_rank', '—')}"
    )
    _show_schedule_metrics("This area", sch, summary["person_hours"], summary["remaining_m"])

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Cables", f"{summary['cables']}")
    c2.metric("Pulled %", f"{summary['pulled_pct']:.1f}%")
    c3.metric("Thick / Thin", f"{summary['thick']} / {summary['thin']}")
    c4.metric("Through", f"{summary['through']} (T{summary['thick_through']}/t{summary['thin_through']})")
    c5.metric("Terminate", f"{summary['terminate']} (T{summary['thick_terminate']}/t{summary['thin_terminate']})")
    c6.metric("Stops here", f"{summary['stop']}")

    st.markdown("**Cable trays**")
    st.code("; ".join(area.trays) or "—")
    st.markdown("**Penetrations**")
    st.code("; ".join(area.penetrations) or "—")

    st.markdown("### Stützen")
    st.caption("Tick installed Stützen (rack hung). % = cables through this Stütze that are past it / verlegt.")
    installed = {node_key(x) for x in (settings.get("installed") or {}).get(area.key, [])}
    if not summary["stuetzen"]:
        st.info("No Stützen (EDV/EDH) listed for this area.")
    else:
        for row in summary["stuetzen"]:
            st_name = row["stuetze"]
            col_a, col_b, col_c = st.columns([3, 2, 2])
            checked = node_key(st_name) in installed
            new_val = col_a.checkbox(
                f"{st_name}",
                value=checked,
                key=f"st_inst_{area.key}_{node_key(st_name)}",
                help="Installed / kirakva",
            )
            if new_val != checked:
                _set_installed(settings, area.key, st_name, new_val)
                st.rerun()
            pct_label = f"{row['pct']:.0f}% ({row['done']}/{row['cables']})"
            if row["complete"] and row["cables"] > 0:
                col_b.success(pct_label + " · 100%")
            else:
                col_b.write(pct_label)
            col_c.caption("installed" if new_val else "not installed")

    st.markdown("### Blocking")
    blocks = list(settings.get("blocks") or [])
    area_entity = f"area:{area.key}"
    area_blocked = area_entity in blocks
    if st.checkbox("Block entire area", value=area_blocked, key=f"block_area_{area.key}"):
        if not area_blocked:
            _toggle_block(settings, area_entity, True)
            st.rerun()
    elif area_blocked:
        _toggle_block(settings, area_entity, False)
        st.rerun()

    if area.trays:
        st.markdown("Block cable trays")
        for tray in area.trays:
            ent = f"tray:{tray}"
            on = ent in blocks
            if st.checkbox(tray, value=on, key=f"block_tray_{area.key}_{node_key(tray)}"):
                if not on:
                    _toggle_block(settings, ent, True)
                    st.rerun()
            elif on:
                _toggle_block(settings, ent, False)
                st.rerun()
    if area.penetrations:
        st.markdown("Block penetrations")
        for pen in area.penetrations:
            ent = f"pen:{pen}"
            on = ent in blocks
            if st.checkbox(pen, value=on, key=f"block_pen_{area.key}_{node_key(pen)}"):
                if not on:
                    _toggle_block(settings, ent, True)
                    st.rerun()
            elif on:
                _toggle_block(settings, ent, False)
                st.rerun()

    active_local = [
        ent
        for ent in (
            [area_entity]
            + [f"tray:{t}" for t in area.trays]
            + [f"pen:{p}" for p in area.penetrations]
        )
        if ent in blocks
    ]
    for ent in active_local:
        affected = affected_areas(ent, areas, summaries, df)
        if affected:
            st.warning(
                f"Blocked `{ent}` affects {len(affected)} other area(s): "
                + ", ".join(f"{a.name} ({a.deck})" for a in affected)
            )
        else:
            st.info(f"Blocked `{ent}` — no other areas share cables.")

    st.markdown("### Cables in this area")
    ids = set(summary["cable_ids"])
    if not ids:
        st.info("No cables match this area’s trays/penetrations.")
        return
    id_col = "Kabelnr" if "Kabelnr" in df.columns else None
    if id_col is None:
        st.dataframe(df, use_container_width=True, hide_index=True)
        return
    view = df[df[id_col].astype(str).isin(ids)].copy()
    rem_map = {info["kabelnr"]: info for _row, info in summary["cable_infos"]}
    view["Area_role"] = view[id_col].astype(str).map(
        lambda k: (
            ("stop " if rem_map.get(k, {}).get("stop") else "")
            + ("terminate" if rem_map.get(k, {}).get("terminate") else "through")
        ).strip()
    )
    view["Area_remaining_m"] = view[id_col].astype(str).map(
        lambda k: rem_map.get(k, {}).get("remaining_m", 0.0)
    )
    show_cols = [c for c in visible_columns(view) if c in view.columns]
    extra = [c for c in ("Area_role", "Area_remaining_m") if c in view.columns]
    st.dataframe(view[show_cols + extra], use_container_width=True, hide_index=True)

    remaining = remaining_cables_frame(summary, df)
    st.markdown("### Export")
    st.caption(
        f"All cables in area: **{len(view)}**. "
        f"Still remaining in this area (`Area_remaining_m` > 0): **{len(remaining)}**."
    )
    e1, e2 = st.columns(2)
    with e1:
        st.markdown("**All cables in area**")
        cable_export_buttons(view, f"area_{area.key}", f"area_{area.name}")
    with e2:
        st.markdown("**Remaining cables only**")
        st.caption("Cables with remaining meters left in this area.")
        if remaining.empty:
            st.info("Nothing left to pull in this area.")
        else:
            stem = safe_filename(f"area_{area.name}_{area.deck}_remaining")
            st.download_button(
                "Kurzliste (remaining)",
                data=kurzliste_xlsx(remaining),
                file_name=f"{stem}_kurzliste.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                key=f"area_rem_kurz_{area.key}",
                help="Shortlist of cables that still have remaining meters in this area.",
            )
            header = st.session_state.get("catra_header") or None
            st.download_button(
                "CaTra pull card (remaining)",
                data=catra_list_xlsx(remaining, header),
                file_name=f"{stem}_huzokartya.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"area_rem_catra_{area.key}",
            )


def render() -> None:
    st.title("Areas")
    st.caption(
        "Room / deck progress from Helység adatok trays & penetrations matched to CaTra Pfad. "
        "Hours use remaining pull meters (full length if not started) plus unchecked Stützen. "
        "Cable pullers are a shared pool; each room uses at most Max pullers / room. "
        "Order = manual priority, else highest Pulled %."
    )

    areas = _ensure_areas_loaded()
    df = st.session_state.get("joined")
    if df is None:
        st.info("Upload Progressliste + CaTra in the sidebar.")
        return
    if not areas:
        st.info("Upload the Areas / Helység Excel in the sidebar.")
        return

    render_filters(df)
    view = filtered_frame(df)
    settings = _load_settings()
    plan = _planning_bar(settings)
    priority_map = dict(settings.get("priority") or {})

    summaries = summarize_all_areas(
        areas,
        view,
        installed_by_area=settings.get("installed") or {},
        thin_pace=plan["thin_pace"],
        thick_pace=plan["thick_pace"],
        h_per_stuetze=plan["h_per_stuetze"],
        pullers=plan["pullers"],
        hours_per_week=plan["hours_per_week"],
        max_per_room=plan["max_per_room"],
        as_of=plan["as_of"],
        priority_map=priority_map,
    )
    totals = totals_from_summaries(
        summaries,
        pullers=plan["pullers"],
        hours_per_week=plan["hours_per_week"],
        as_of=plan["as_of"],
    )
    _show_schedule_metrics(
        "All areas (parallel schedule)",
        totals["schedule"],
        totals["person_hours"],
        totals["remaining_m"],
    )
    t1, t2, t3 = st.columns(3)
    t1.metric("Cables (sum of area hits)", f"{totals['cables']}")
    t2.metric("Pulled % (sum)", f"{totals['pulled_pct']:.1f}%")
    t3.metric(
        "Pool capacity",
        f"{totals['schedule']['weekly_capacity']:,.0f} h/week "
        f"({plan['pullers']} pullers · ≤{plan['max_per_room']}/room)",
    )

    with st.expander("Set area priority", expanded=False):
        _priority_editor(summaries, settings)

    table = _overview_table(summaries, settings.get("blocks") or [], priority_map)
    display = table.drop(columns=["_key"], errors="ignore")
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("### From zero (full room)")
    st.caption(
        "Full Length_m for every cable in the room (ignore current pull) plus all Stützen hours. "
        "Weeks use max pullers/room crew at current weekly hours."
    )
    zero_table = _from_zero_table(summaries)
    st.dataframe(zero_table, use_container_width=True, hide_index=True)

    labels = {
        s["area"].key: (
            f"{s['area'].name} · {s['area'].deck}"
            + (f" ({s['area'].area_ids})" if s["area"].area_ids else "")
        )
        for s in summaries
    }
    keys = list(labels.keys())
    if not keys:
        st.info("No areas with trays or penetrations to show.")
        return
    selected = st.selectbox(
        "Area detail",
        keys,
        format_func=lambda k: labels.get(k, k),
        key="areas_detail_key",
    )
    summary = next(s for s in summaries if s["area"].key == selected)
    _render_detail(summary, areas, summaries, view, settings, plan)
