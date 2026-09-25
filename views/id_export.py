from __future__ import annotations

import streamlit as st

from src.ids import cable_id_list_stats, select_cables_by_ids
from src.ui import cable_export_buttons, copy_to_clipboard_button, visible_columns


def render() -> None:
    st.title("Cable ID export")
    st.caption(
        "Paste cable numbers separated by semicolons (or new lines). "
        "Example: `5012.1; 0006; 3602; 5012,1`. "
        "Then export one combined CaTra pull card or Kurzliste. "
        "`5012.1` and `5012,1` count as the same ID."
    )

    df = st.session_state.get("joined")
    if df is None:
        st.info("Upload both Excel files in the sidebar.")
        return

    text = st.text_area(
        "Cable numbers",
        placeholder="5012.1; 0006; 3602; 5012,1",
        height=140,
        key="id_export_list",
        help="Separate with ; or new lines.",
    )

    stats = cable_id_list_stats(text)
    remove_dupes = st.checkbox(
        "Remove duplicate IDs",
        value=True,
        key="id_export_dedupe",
        help="Keep the first occurrence of each cable ID.",
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("IDs pasted", f"{stats['raw_count']}")
    c2.metric("Unique IDs", f"{stats['unique_count']}")
    c3.metric("Duplicates removed", f"{stats['duplicate_count']}" if remove_dupes else "0 (kept)")

    wanted = stats["unique"] if remove_dupes else stats["raw"]
    if wanted and remove_dupes:
        cleaned = "; ".join(wanted)
        copy_to_clipboard_button(cleaned, key="id_export_copy_cleaned", label="Copy cleaned ID list")

    if st.button("Search / preview", type="primary") or st.session_state.get("id_export_auto"):
        matched, found, missing = select_cables_by_ids(df, text, dedupe=remove_dupes)
        st.session_state["id_export_matched"] = matched
        st.session_state["id_export_found"] = found
        st.session_state["id_export_missing"] = missing
        st.session_state["id_export_dedupe_used"] = remove_dupes
        st.session_state["id_export_auto"] = True

    matched = st.session_state.get("id_export_matched")
    if matched is None:
        st.info("Paste the cable numbers, then click Search / preview.")
        return

    found = st.session_state.get("id_export_found") or []
    missing = st.session_state.get("id_export_missing") or []

    m1, m2, m3 = st.columns(3)
    m1.metric("Requested IDs", f"{len(found) + len(missing)}")
    m2.metric("Found", f"{len(found)}")
    m3.metric("Missing", f"{len(missing)}")

    if missing:
        st.warning("Not found: " + "; ".join(missing))
    if matched.empty:
        st.error("No cables to export.")
        return

    st.subheader("Matched cables")
    st.dataframe(matched[visible_columns(matched)], use_container_width=True, hide_index=True)

    st.subheader("Export")
    st.caption("CaTra pull card = pathway layout · Kurzliste = one row per cable with pathway.")
    export_key = "id_list_" + "_".join(found) if found else "id_list_empty"
    cable_export_buttons(matched, "id_export", export_key)
