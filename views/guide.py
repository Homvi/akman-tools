from __future__ import annotations

import streamlit as st


def _link(page_key: str, label: str) -> None:
    page = (st.session_state.get("_pages") or {}).get(page_key)
    if page is not None:
        st.page_link(page, label=label)
        return
    st.page_link(f"/{page_key}", label=label)


def render() -> None:
    st.title("Hogyan működik")
    st.caption("Röviden. A link a funkcióhoz visz.")

    st.markdown("**Adat** az oldalsávban: Progressliste + CaTra Kabelliste. Egyszer kell feltölteni.")
    st.markdown("**Szűrők** (Gerät, vastagság, kategória, Stütze) minden oldalon ugyanazok.")

    st.subheader("Oldalak")
    _link("cables", "All cables — másolható listák, húzókártya / Kurzliste export")
    _link("stopped", "Stopped cables — jelenlegi megállás, húzókártya / Kurzliste")
    _link("stutzen", "Stütze / Bahn szűrő — AND/OR a nyomvonal pontjaira, húzókártya export")
    _link("id_export", "Kábel ID export — pontosvesszős lista → húzókártya / Kurzliste")
    _link("routes", "Nyomvonal-csoportok — 90% path-egyezés, húzókártya / Kurzliste")
    _link("progress", "Progress — napi és heti (KW) behúzott méter")
    _link("calculator", "Hossz kalkulátor — részlegesen behúzott szakasz métere")

    st.subheader("Fogalmak")
    st.markdown(
        """
- **Behúzott:** van `verlegt` dátum.
- **Elindított:** van Startsegment, de még nincs kész.
- **Stütze:** EDV / EDH pont a nyomvonalon.
- **Nyomvonal:** CaTra path, KA / KE / Ring nélkül.
- **Húzókártya:** CaTra 4-soros lap, nyomvonal külön sorban.
- **Kurzliste:** minden kábel egy sorban, nyomvonallal.
- **Stütze / Bahn szűrő:** AND/OR a nyomvonal pontjaira, húzókártya / Kurzliste export.
- **Kábel ID export:** pontosvesszős lista; `5012.1` = `5012,1`.
- **Hossz kalkulátor:** start–vég szakasz távolságai + A/E ráhagyás.
"""
    )
