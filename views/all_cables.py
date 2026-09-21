from __future__ import annotations

import streamlit as st

from src.analysis import (
    cable_numbers_by_type,
    cable_type_series,
    long_list_cables,
    pulled_cables,
    started_cables,
    total_length,
)
from src.runtime import get_filtered
from src.ui import cable_number_copy_box, cable_export_buttons, filtered_frame, render_filters, visible_columns


def _active_filter_count() -> int:
    count = 0
    if st.session_state.get("filter_devices"):
        count += 1
    if st.session_state.get("pull_not") or st.session_state.get("pull_partial") or st.session_state.get("pull_yes"):
        count += 1
    if st.session_state.get("filter_thickness"):
        count += 1
    if st.session_state.get("filter_category") not in (None, "All"):
        count += 1
    if st.session_state.get("filter_stop_stuetzen"):
        count += 1
    return count


def render() -> None:
    df = st.session_state.get("joined")
    if df is None:
        st.title("All cables")
        st.info("Töltsd fel mindkét Excel fájlt az oldalsávban.")
        return

    render_filters(df)
    view = filtered_frame(df)
    listing = get_filtered(df, ignore_pull=True)
    st.title("All cables")
    c1, c2, c3 = st.columns(3)
    c1.metric("Cables shown", f"{len(view):,}")
    c2.metric(
        "Total length (m)",
        f"{total_length(view):,.1f}",
        help="Pulled: teljes kábelhossz. Részlegesen: csak a ténylegesen behúzott méter.",
    )
    c3.metric("Filters active", _active_filter_count())

    st.dataframe(view[visible_columns(view)], use_container_width=True, hide_index=True)
    cable_export_buttons(view, "cables_filtered", "all_cables")

    pulled = pulled_cables(listing)
    started = started_cables(listing)
    left, right = st.columns(2)
    with left:
        cable_number_copy_box("Behúzott kábelek", pulled, key="pulled")
        st.caption("Van verlegt dátum.")
    with right:
        cable_number_copy_box("Elindított kábelek", started, key="started")
        st.caption("Van Startsegment, de még nincs kész.")

    long_ones = long_list_cables(view, liste="001", min_m=150)
    st.subheader("Lista 001, 150 m felett")
    st.caption(
        "001-es lista, 150 m felett, típus és Kabeladern szerint. "
        "Ugyanazok a szűrők érvényesek, mint a táblázatra."
    )
    types = cable_type_series(long_ones)
    by_type = cable_numbers_by_type(long_ones)
    if not by_type:
        st.info("Nincs ilyen kábel a jelenlegi szűrőkkel.")
    else:
        for label in by_type:
            cable_number_copy_box(
                label,
                long_ones.loc[types.eq(label)],
                key=f"list001_{label}",
            )
