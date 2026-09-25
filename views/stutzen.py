from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from src.export import catra_list_xlsx, kurzliste_xlsx, safe_filename
from src.stutzen_filter import (
    MODE_AND,
    MODE_LABELS,
    MODE_OR,
    criteria_header,
    filter_by_nodes,
    parse_search_nodes,
    preview_cards_html,
    preview_rows,
    search_nodes_stats,
    stutzen_filename,
    total_preview_length,
)


def render() -> None:
    df = st.session_state.get("joined")
    st.title("Stütze / Bahn szűrő")
    st.caption(
        "Paste all Stütze / Bahn numbers separated by `;` (comma or new line also works). "
        "Optionally keep unique numbers only, then filter cables (AND = all, OR = any) and export."
    )
    if df is None:
        st.info("Upload both Excel files in the sidebar.")
        return

    nodes_text = st.text_area(
        "Stütze / Bahn numbers",
        placeholder="1EDV606.1; 1EDV606; 3EDH407; 1EDV606",
        height=140,
        help="Separate with ; or new lines. You can paste a long list and tick unique-only below.",
        key="stutzen_search",
    )
    stats = search_nodes_stats(nodes_text)
    unique_only = st.checkbox(
        "Only unique numbers",
        value=True,
        key="stutzen_unique_only",
        help="Keep the first occurrence of each Stütze / Bahn number and drop repeats from the filter list.",
    )
    mode_label = st.selectbox("Filter logic", list(MODE_LABELS.values()), key="stutzen_mode_label")
    mode = MODE_AND if mode_label == MODE_LABELS[MODE_AND] else MODE_OR

    nodes = parse_search_nodes(nodes_text, unique_only=unique_only)
    m1, m2, m3 = st.columns(3)
    m1.metric("Numbers pasted", f"{stats['raw_count']}")
    m2.metric("Unique numbers", f"{stats['unique_count']}")
    m3.metric("Duplicates dropped", f"{stats['duplicate_count']}" if unique_only else "0 (kept)")
    if stats["duplicates"]:
        st.caption("Repeated in paste: " + "; ".join(stats["duplicates"]))
    if nodes:
        st.caption("Active filter list: `" + "; ".join(nodes) + "`")
    st.caption(f"Export file name: `{stutzen_filename(nodes)}`")

    if st.button("Filter & preview", type="primary"):
        if not nodes:
            st.session_state.pop("stutzen_hits", None)
            st.error("Enter at least one Stütze / Bahn number.")
        else:
            hits = filter_by_nodes(df, nodes, mode)
            st.session_state["stutzen_hits"] = hits
            st.session_state["stutzen_nodes"] = nodes
            st.session_state["stutzen_mode"] = mode
            st.session_state["stutzen_unique_used"] = unique_only

    hits = st.session_state.get("stutzen_hits")
    used_nodes = st.session_state.get("stutzen_nodes") or nodes
    used_mode = st.session_state.get("stutzen_mode") or mode
    if hits is None:
        return

    rows = preview_rows(hits)
    total_m = total_preview_length(rows)
    c1, c2, c3 = st.columns(3)
    c1.metric("Matched cables", f"{len(rows)}")
    c2.metric("Total length", f"{total_m:,.1f} m")
    c3.metric("Filtered Stützen / Bahn", ", ".join(used_nodes) or "—")

    if hits.empty:
        st.info("No cables match this filter.")
        return

    header = criteria_header(st.session_state.get("catra_header"), used_nodes, used_mode)
    fname = stutzen_filename(used_nodes)
    left, right = st.columns(2)
    with left:
        st.download_button(
            "Export Excel (CaTra pull card)",
            data=catra_list_xlsx(hits, header),
            file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
    with right:
        st.download_button(
            "Kurzliste",
            data=kurzliste_xlsx(hits),
            file_name=f"{safe_filename(fname.rsplit('.', 1)[0])}_kurzliste.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.subheader("Cable preview")
    components.html(preview_cards_html(rows, used_nodes), height=620, scrolling=True)
