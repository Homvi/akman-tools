from __future__ import annotations

import streamlit as st

from src.analysis import PULL_NOT, PULL_PARTIAL
from src.export import safe_filename
from src.pathways import (
    GROUP_MODES,
    MODE_SIM,
    cables_in_group,
    group_display_columns,
    stop_groups,
)
from src.runtime import get_route_groups
from src.ui import cable_export_buttons, filtered_frame, render_filters

_PAGE_SIZE = 20
_CABLE_COLS = (
    "Kabelnr",
    "Pull_status",
    "Category",
    "Thickness",
    "Point_A",
    "Point_E",
    "Stuetzen_text",
    "Pfad",
    "Length_m",
    "Remaining_m",
    "Geraet_A",
    "Geraet_E",
)


@st.fragment
def _group_card(row, view, start: int, offset: int) -> None:
    cables = cables_in_group(view, row.join_keys)
    unpulled = cables[cables["Pull_status"].isin([PULL_NOT, PULL_PARTIAL])]
    title = f"{row.Group} · {int(row.Cable_count)} kábel · {row.Total_m:.0f} m"
    st.markdown(f"**{title}**")
    fname = f"route_{start + offset}_{safe_filename(str(row.Group))}"
    cable_export_buttons(cables, fname, f"gexp_{start}_{offset}")
    with st.expander("Kábelek és nyomvonal", expanded=False):
        point_a = getattr(row, "Point_A", "")
        point_e = getattr(row, "Point_E", "")
        if point_a or point_e:
            st.write(f"A **{point_a}** → E **{point_e}**")
        stuetzen = getattr(row, "Stuetzen", "")
        if stuetzen:
            st.write(f"Közös szakasz: **{stuetzen}**")
        st.write(f"{len(cables)} kábel, ebből {len(unpulled)} nincs kész.")
        visible = [col for col in _CABLE_COLS if col in cables.columns]
        st.dataframe(cables[visible], use_container_width=True, hide_index=True)
        if not unpulled.empty:
            st.caption("Még nem behúzottak")
            cable_export_buttons(unpulled, f"unpulled_{fname}", f"gexp_u_{start}_{offset}")
        stops = stop_groups(cables)
        if not stops.empty:
            st.caption("Azonos megállás")
            st.dataframe(stops.drop(columns=["join_keys"]), use_container_width=True, hide_index=True)


def render() -> None:
    df = st.session_state.get("joined")
    if df is None:
        st.title("Nyomvonal-csoportok")
        st.info("Töltsd fel mindkét Excel fájlt az oldalsávban.")
        return

    render_filters(df)
    view = filtered_frame(df)

    st.title("Nyomvonal-csoportok")
    st.success("Új csoportosítás: KA / KE / Ring nélkül, 90% path-egyezés.")
    st.caption(
        "Csak valódi bán pontok (pl. 1E2104, 2EDV208). "
        "Egy csoportba azok a kábelek kerülnek, amelyek nyomvonala legalább 90%-ban egyezik. "
        "Az export: húzókártya (CaTra, nyomvonal külön sorban) vagy Kurzliste (egy sor / kábel). "
        "Az oldalsávban a Megállva Stütze szűrővel csak egy adott Stützén megállt kábeleket látod."
    )
    picked = st.session_state.get("filter_stop_stuetzen") or []
    if picked:
        st.info("Szűrve, megállva itt: " + ", ".join(picked))

    c1, c2, c3 = st.columns(3)
    mode = c1.selectbox("Csoportosítás", GROUP_MODES, index=0)
    min_size = c2.slider("Minimum kábel egy csoportban", min_value=2, max_value=10, value=2)
    only_unpulled_groups = c3.checkbox("Csak ahol van még nem behúzott", value=True)
    similarity = 0.9
    if mode == MODE_SIM:
        similarity = st.slider("Minimális egyezés", min_value=0.70, max_value=1.0, value=0.90, step=0.05)

    groups = get_route_groups(view, mode=mode, min_size=min_size, similarity=similarity)
    if not groups.empty and only_unpulled_groups:
        groups = groups[groups["Unpulled_count"] > 0]
    if groups.empty:
        st.info("Nincs ilyen nyomvonal-csoport a jelenlegi szűrőkkel.")
        return

    st.metric("Csoportok", f"{len(groups):,}")
    st.dataframe(groups[group_display_columns(groups)], use_container_width=True, hide_index=True)

    pages = max(1, (len(groups) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = st.number_input("Oldal", min_value=1, max_value=pages, value=1)
    start = (page - 1) * _PAGE_SIZE
    chunk = groups.iloc[start : start + _PAGE_SIZE]

    st.subheader("Csoportok exporttal")
    st.caption(f"{start + 1}–{start + len(chunk)} / {len(groups)}")
    for offset, row in enumerate(chunk.itertuples()):
        _group_card(row, view, start, offset)
