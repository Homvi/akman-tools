from __future__ import annotations

import pandas as pd

from src.analysis import assign_pull_status
from src.categories import extract_k_category, thickness_label


def join_cable_data(status: pd.DataFrame, catra: pd.DataFrame) -> pd.DataFrame:
    left = status.copy()
    right = catra.copy()
    if "join_key" not in left.columns or "join_key" not in right.columns:
        raise ValueError("Both datasets need a join_key column.")

    right_keep = [
        col
        for col in right.columns
        if col == "join_key" or col not in left.columns
    ]
    merged = left.merge(right[right_keep], on="join_key", how="left", indicator=True)
    merged["match"] = merged["_merge"].eq("both")
    merged = merged.drop(columns="_merge")

    merged["Length_m"] = pd.to_numeric(merged.get("Zuschn"), errors="coerce")
    if "Laenge" in merged.columns:
        merged["Length_m"] = merged["Length_m"].fillna(pd.to_numeric(merged["Laenge"], errors="coerce"))

    adern = merged["Kabeladern"] if "Kabeladern" in merged.columns else pd.Series("", index=merged.index)
    typ = merged["Typ"] if "Typ" in merged.columns else pd.Series("", index=merged.index)
    merged["Thickness"] = [
        thickness_label(a if pd.notna(a) and str(a).strip() else t)
        for a, t in zip(adern, typ)
    ]

    if "Geraet_A" in merged.columns and "A_Geraet" in merged.columns:
        merged["Geraet_A"] = merged["Geraet_A"].replace("", pd.NA).fillna(merged["A_Geraet"])
    elif "A_Geraet" in merged.columns:
        merged["Geraet_A"] = merged["A_Geraet"]
    if "Geraet_E" in merged.columns and "E_Geraet" in merged.columns:
        merged["Geraet_E"] = merged["Geraet_E"].replace("", pd.NA).fillna(merged["E_Geraet"])
    elif "E_Geraet" in merged.columns:
        merged["Geraet_E"] = merged["E_Geraet"]

    if "Category" not in merged.columns:
        merged["Category"] = "Unclassified"
    if "Kabel_raw" in merged.columns:
        missing = merged["Category"].isna() | merged["Category"].eq("Unclassified")
        merged.loc[missing, "Category"] = merged.loc[missing, "Kabel_raw"].map(extract_k_category)

    pulled_m = pd.to_numeric(merged.get("Total_teilgezogene_meter"), errors="coerce").fillna(0)
    length = pd.to_numeric(merged["Length_m"], errors="coerce")
    merged["Remaining_m"] = (length - pulled_m).clip(lower=0)
    merged["Pulled"] = merged["verlegt"].notna() if "verlegt" in merged.columns else False
    return assign_pull_status(merged)


def unmatched_ids(status: pd.DataFrame, catra: pd.DataFrame) -> tuple[list[str], list[str]]:
    left = set(status["join_key"].dropna())
    right = set(catra["join_key"].dropna())
    only_status = sorted(status.loc[status["join_key"].isin(left - right), "Kabelnr"].dropna().unique())
    only_catra = sorted(catra.loc[catra["join_key"].isin(right - left), "Kabel"].dropna().unique())
    return only_status, only_catra
