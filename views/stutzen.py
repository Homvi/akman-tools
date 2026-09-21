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
    stutzen_filename,
    total_preview_length,
)


def render() -> None:
    df = st.session_state.get("joined")
    st.title("Stütze / Bahn szűrő")
    st.caption(
        "Kábelek szűrése Stütze vagy bán pontokra a nyomvonalon. "
        "Ugyanaz a logika, mint a CaTra kábellista szűrőben: AND = mind, OR = bármelyik."
    )
    if df is None:
        st.info("Töltsd fel mindkét Excel fájlt az oldalsávban.")
        return

    nodes_text = st.text_input(
        "Keresett kábelbánok / Stützen",
        placeholder="pl. 1EDV606.1, 1EDV606",
        help="Több elemet vesszővel válassz el.",
        key="stutzen_search",
    )
    mode_label = st.selectbox("Szűrési logika", list(MODE_LABELS.values()), key="stutzen_mode_label")
    mode = MODE_AND if mode_label == MODE_LABELS[MODE_AND] else MODE_OR
    nodes = parse_search_nodes(nodes_text)
    st.caption(f"Exportált fájlnév: `{stutzen_filename(nodes)}`")

    if st.button("Szűrés & Előnézet", type="primary"):
        if not nodes:
            st.session_state.pop("stutzen_hits", None)
            st.error("Adj meg legalább egy szűrési feltételt.")
        else:
            hits = filter_by_nodes(df, nodes, mode)
            st.session_state["stutzen_hits"] = hits
            st.session_state["stutzen_nodes"] = nodes
            st.session_state["stutzen_mode"] = mode

    hits = st.session_state.get("stutzen_hits")
    used_nodes = st.session_state.get("stutzen_nodes") or nodes
    used_mode = st.session_state.get("stutzen_mode") or mode
    if hits is None:
        return

    rows = preview_rows(hits)
    total_m = total_preview_length(rows)
    c1, c2, c3 = st.columns(3)
    c1.metric("Talált kábelek", f"{len(rows)} db")
    c2.metric("Összesen hossz", f"{total_m:,.1f} m")
    c3.metric("Szűrt Stützen / Bán", ", ".join(used_nodes) or "—")

    if hits.empty:
        st.info("Nincs a szűrésnek megfelelő kábel.")
        return

    header = criteria_header(st.session_state.get("catra_header"), used_nodes, used_mode)
    fname = stutzen_filename(used_nodes)
    left, right = st.columns(2)
    with left:
        st.download_button(
            "Exportálás Excelbe (Húzókártya)",
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

    st.subheader("Kábelek előnézete")
    components.html(preview_cards_html(rows, used_nodes), height=620, scrolling=True)
