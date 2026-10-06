from __future__ import annotations

import re

import pandas as pd

from src.join import unmatched_ids

LENGTH_TOLERANCE_M = 0.1

_LISTE_NUM = re.compile(r"(\d+)")


def _blank(value) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "<na>", "none"}


def _norm_text(value) -> str:
    if _blank(value):
        return ""
    return str(value).strip().casefold()


def _norm_liste(value) -> str:
    """Compare list ids loosely: L0005 / 0005 / 5 → same digit core when possible."""
    if _blank(value):
        return ""
    text = str(value).strip()
    token = text.split()[0] if text.split() else text
    m = _LISTE_NUM.search(token)
    if not m:
        return _norm_text(text)
    return str(int(m.group(1)))


def enrich_joined_for_reconcile(status: pd.DataFrame, catra: pd.DataFrame, joined: pd.DataFrame) -> pd.DataFrame:
    """Attach progress/gesamt Liste side-by-side for conflict checks after join."""
    out = joined.copy()
    if "join_key" not in out.columns:
        return out
    status_liste: dict[str, object] = {}
    if "Liste" in status.columns and "join_key" in status.columns:
        status_liste = {
            str(k): v
            for k, v in zip(status["join_key"].astype(str), status["Liste"])
            if not _blank(k)
        }
    catra_liste: dict[str, object] = {}
    if "Liste" in catra.columns and "join_key" in catra.columns:
        catra_liste = {
            str(k): v
            for k, v in zip(catra["join_key"].astype(str), catra["Liste"])
            if not _blank(k)
        }
    keys = out["join_key"].astype(str)
    out["_liste_progress"] = keys.map(status_liste)
    out["_liste_gesamt"] = keys.map(catra_liste)
    return out


def field_mismatches(
    joined: pd.DataFrame,
    *,
    length_tolerance_m: float = LENGTH_TOLERANCE_M,
) -> pd.DataFrame:
    """
    Compare Progressliste vs Gesamtliste fields on matched cables.
    Returns columns: Kabelnr, field, progress_value, gesamt_value.
    """
    empty = pd.DataFrame(columns=["Kabelnr", "field", "progress_value", "gesamt_value"])
    if joined is None or joined.empty:
        return empty

    frame = joined
    if "match" in frame.columns:
        frame = frame[frame["match"].fillna(False)].copy()
    if frame.empty:
        return empty

    rows: list[dict] = []
    for _, row in frame.iterrows():
        kabel = row.get("Kabelnr")
        if _blank(kabel):
            kabel = row.get("Kabel")
        kabel = "" if _blank(kabel) else str(kabel)

        if "Zuschn" in frame.columns and "Laenge" in frame.columns:
            left = pd.to_numeric(row.get("Zuschn"), errors="coerce")
            right = pd.to_numeric(row.get("Laenge"), errors="coerce")
            if pd.notna(left) and pd.notna(right):
                if abs(float(left) - float(right)) > float(length_tolerance_m):
                    rows.append(
                        {
                            "Kabelnr": kabel,
                            "field": "Length_m",
                            "progress_value": float(left),
                            "gesamt_value": float(right),
                        }
                    )

        if "A_Geraet" in frame.columns and "Geraet_A" in frame.columns:
            pv, gv = row.get("A_Geraet"), row.get("Geraet_A")
            if not _blank(pv) and not _blank(gv) and _norm_text(pv) != _norm_text(gv):
                rows.append(
                    {
                        "Kabelnr": kabel,
                        "field": "A_Geraet",
                        "progress_value": str(pv).strip(),
                        "gesamt_value": str(gv).strip(),
                    }
                )

        if "E_Geraet" in frame.columns and "Geraet_E" in frame.columns:
            pv, gv = row.get("E_Geraet"), row.get("Geraet_E")
            if not _blank(pv) and not _blank(gv) and _norm_text(pv) != _norm_text(gv):
                rows.append(
                    {
                        "Kabelnr": kabel,
                        "field": "E_Geraet",
                        "progress_value": str(pv).strip(),
                        "gesamt_value": str(gv).strip(),
                    }
                )

        if "_liste_progress" in frame.columns and "_liste_gesamt" in frame.columns:
            pv, gv = row.get("_liste_progress"), row.get("_liste_gesamt")
            if not _blank(pv) and not _blank(gv) and _norm_liste(pv) != _norm_liste(gv):
                rows.append(
                    {
                        "Kabelnr": kabel,
                        "field": "Liste",
                        "progress_value": str(pv).strip(),
                        "gesamt_value": str(gv).strip(),
                    }
                )

    return pd.DataFrame(rows, columns=["Kabelnr", "field", "progress_value", "gesamt_value"])


def reconcile_report(
    status: pd.DataFrame,
    catra: pd.DataFrame,
    joined: pd.DataFrame | None = None,
    *,
    length_tolerance_m: float = LENGTH_TOLERANCE_M,
) -> dict:
    """Full Progressliste ↔ Gesamtliste mismatch report."""
    only_status, only_catra = unmatched_ids(status, catra)
    if joined is None:
        from src.join import join_cable_data

        joined = join_cable_data(status, catra)
    enriched = enrich_joined_for_reconcile(status, catra, joined)
    conflicts = field_mismatches(enriched, length_tolerance_m=length_tolerance_m)
    return {
        "only_status": only_status,
        "only_catra": only_catra,
        "field_conflicts": conflicts,
        "joined": enriched,
    }
