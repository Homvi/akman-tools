from __future__ import annotations

import streamlit as st

from src.ids import parse_cable_id_list, select_cables_by_ids
from src.ui import cable_export_buttons, visible_columns


def render() -> None:
    st.title("Kábel ID export")
    st.caption(
        "Pontosvesszővel (vagy soronként) elválasztott kábelszámok. "
        "5012.1 és 5012,1 ugyanaz. Húzókártya = CaTra nyomvonallal, Kurzliste = egy sor / kábel."
    )

    df = st.session_state.get("joined")
    if df is None:
        st.info("Töltsd fel mindkét Excel fájlt az oldalsávban.")
        return

    text = st.text_area(
        "Kábelszámok",
        placeholder="5012.1; 0006; 3602; 5012,1",
        height=140,
        key="id_export_list",
        help="Pontosvessző vagy új sor. A . és , a tizedesjelben egyenértékű.",
    )

    wanted = parse_cable_id_list(text)
    st.caption(f"{len(wanted)} egyedi ID a listából (duplikátumok összevonva).")

    if st.button("Keresés / előnézet", type="primary") or st.session_state.get("id_export_auto"):
        matched, found, missing = select_cables_by_ids(df, text)
        st.session_state["id_export_matched"] = matched
        st.session_state["id_export_found"] = found
        st.session_state["id_export_missing"] = missing
        st.session_state["id_export_auto"] = True

    matched = st.session_state.get("id_export_matched")
    if matched is None:
        st.info("Írd be a kábelszámokat, majd kattints a Keresés / előnézet gombra.")
        return

    found = st.session_state.get("id_export_found") or []
    missing = st.session_state.get("id_export_missing") or []

    c1, c2, c3 = st.columns(3)
    c1.metric("Kért ID-k", f"{len(found) + len(missing)}")
    c2.metric("Találat", f"{len(found)}")
    c3.metric("Hiányzik", f"{len(missing)}")

    if missing:
        st.warning("Nem található: " + "; ".join(missing))
    if matched.empty:
        st.error("Nincs exportálható kábel.")
        return

    st.subheader("Talált kábelek")
    st.dataframe(matched[visible_columns(matched)], use_container_width=True, hide_index=True)

    st.subheader("Export")
    st.caption("Húzókártya (CaTra) = nyomvonallal · Kurzliste = tömör lista nyomvonallal egy sorban.")
    # Key includes found IDs so a previous selection cannot reuse the prepared xlsx.
    export_key = "id_list_" + "_".join(found) if found else "id_list_empty"
    cable_export_buttons(matched, "id_export", export_key)
