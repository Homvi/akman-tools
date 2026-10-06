from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from src.reconcile import field_mismatches
from src.ui import download_button


def _id_table(ids: list, label: str) -> pd.DataFrame:
    return pd.DataFrame({label: list(ids)})


def render() -> None:
    st.title("Hibák")
    st.caption(
        "Progressliste ↔ Gesamtliste (CaTra / Kabelziehliste) eltérések: "
        "csak az egyik listában lévő kábelek, plusz hossz / eszköz / Liste ütközések."
    )

    joined = st.session_state.get("joined")
    if joined is None:
        st.info("Upload Progressliste + CaTra / Gesamtliste in the sidebar.")
        return

    only_status = list(st.session_state.get("only_status") or [])
    only_catra = list(st.session_state.get("only_catra") or [])
    conflicts = st.session_state.get("field_conflicts")
    if conflicts is None or not isinstance(conflicts, pd.DataFrame):
        conflicts = field_mismatches(joined)

    m1, m2, m3 = st.columns(3)
    m1.metric("Only Progressliste", len(only_status))
    m2.metric("Only Gesamtliste", len(only_catra))
    m3.metric("Field conflicts", len(conflicts))

    status_name = st.session_state.get("status_name") or "Progressliste"
    catra_name = st.session_state.get("catra_name") or "Gesamtliste"
    st.caption(f"Compared: `{status_name}` vs `{catra_name}`. Length tolerance ±0.1 m.")

    st.subheader("Only in Progressliste")
    if only_status:
        t1 = _id_table(only_status, "Kabelnr")
        st.dataframe(t1, use_container_width=True, hide_index=True)
        download_button(t1, "Export only Progressliste", "errors_only_progressliste.xlsx")
    else:
        st.success("Every Progressliste cable has a Gesamtliste match.")

    st.subheader("Only in Gesamtliste")
    if only_catra:
        t2 = _id_table(only_catra, "Kabel")
        st.dataframe(t2, use_container_width=True, hide_index=True)
        download_button(t2, "Export only Gesamtliste", "errors_only_gesamtliste.xlsx")
    else:
        st.success("Every Gesamtliste cable has a Progressliste match.")

    st.subheader("Field conflicts (matched cables)")
    st.caption("Length (Zuschn vs Länge), A/E Gerät, Liste — only when both sides have a value.")
    if conflicts is not None and not conflicts.empty:
        show = conflicts.rename(
            columns={
                "progress_value": "Progressliste",
                "gesamt_value": "Gesamtliste",
            }
        )
        st.dataframe(show, use_container_width=True, hide_index=True)
        download_button(show, "Export field conflicts", "errors_field_conflicts.xlsx")

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            _id_table(only_status, "Kabelnr").to_excel(writer, index=False, sheet_name="Only_Progress")
            _id_table(only_catra, "Kabel").to_excel(writer, index=False, sheet_name="Only_Gesamt")
            show.to_excel(writer, index=False, sheet_name="Field_conflicts")
        st.download_button(
            "Export all Hibák (xlsx)",
            data=buffer.getvalue(),
            file_name="hibak_progress_vs_gesamt.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="errors_all_xlsx",
        )
    else:
        st.success("No field conflicts on matched cables.")
