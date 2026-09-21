from __future__ import annotations

import streamlit as st

from src.export import cables_at_location, catra_locations_zip, safe_filename
from src.pathways import is_stuetze
from src.runtime import get_stop_tables
from src.ui import cable_export_buttons, download_button, filtered_frame, render_filters

_CABLE_COLS = (
    "Kabelnr",
    "Pull_status",
    "Category",
    "Thickness",
    "Stop_location",
    "Point_A",
    "Point_E",
    "Stuetzen_text",
    "Pfad",
    "Length_m",
    "Remaining_m",
    "Geraet_A",
    "Geraet_E",
)


def render() -> None:
    df = st.session_state.get("joined")
    if df is None:
        st.title("Stopped cables")
        st.info("Töltsd fel mindkét Excel fájlt az oldalsávban.")
        return

    render_filters(df)
    view = filtered_frame(df)
    detail, summary = get_stop_tables(view)

    st.title("Stopped cables")
    st.caption(
        "Csak a jelenlegi megállás: a már behúzott szakasz és a kész kábelek kimaradnak. "
        "Ha a megállás a végleges A/E lyuk, azt sem számoljuk."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stop locations", f"{len(summary):,}")
    c2.metric("Stopped cables", f"{detail['Kabelnr'].nunique() if not detail.empty else 0:,}")
    c3.metric(
        "Remaining unpulled (m)",
        f"{float(summary['Remaining_unpulled_m'].sum()) if not summary.empty else 0:,.1f}",
    )
    c4.metric(
        "Total length of stopped cables (m)",
        f"{float(summary['Total_cable_length_m'].sum()) if not summary.empty else 0:,.1f}",
    )

    st.subheader("Kábelek egy Stützénél")
    only_stuetze = st.checkbox("Csak Stütze-megállások (EDV/EDH)", value=True)
    all_locations = summary["Stop_location"].tolist() if not summary.empty else []
    stuetzen = [loc for loc in all_locations if is_stuetze(loc)]
    locations = stuetzen if only_stuetze else all_locations
    if not locations:
        st.info("Nincs megállás a jelenlegi szűrőkkel.")
    else:
        location = st.selectbox("Stütze / megállás", locations)
        header = st.session_state.get("catra_header") or None
        loc_cables = cables_at_location(view, detail, location)
        loc_detail = detail[detail["Stop_location"].astype(str) == str(location)]
        kind = "Stütze" if is_stuetze(location) else "megállás"
        st.write(f"{len(loc_cables)} kábel megállva itt: **{location}** ({kind})")
        visible = [col for col in _CABLE_COLS if col in loc_cables.columns]
        show = loc_cables[visible].copy()
        if "Stop_location" not in show.columns:
            show.insert(4, "Stop_location", location)
        st.dataframe(show, use_container_width=True, hide_index=True)
        cable_export_buttons(loc_cables, f"stopped_{safe_filename(location)}", f"stop_{safe_filename(location)}")
        if not loc_detail.empty:
            st.caption("Megállás adatai")
            st.dataframe(
                loc_detail.drop(columns=["join_key"], errors="ignore"),
                use_container_width=True,
                hide_index=True,
            )

        if st.button("Prepare zip of every location (húzókártya + Kurzliste)", disabled=detail.empty):
            st.session_state["stop_zip"] = catra_locations_zip(
                view, detail, summary["Stop_location"].tolist(), header
            )
        if st.session_state.get("stop_zip"):
            st.download_button(
                "Download zip of every location",
                data=st.session_state["stop_zip"],
                file_name="stopped_by_location.zip",
                mime="application/zip",
            )

    st.subheader("By stop location")
    st.dataframe(summary, use_container_width=True, hide_index=True)
    download_button(summary, "Export stop summary", "stopped_by_location.xlsx")

    st.subheader("Cables at each stop")
    show_all = detail.drop(columns=["join_key"], errors="ignore")
    st.dataframe(show_all, use_container_width=True, hide_index=True)
    download_button(show_all, "Export stopped cables", "stopped_cables.xlsx")
