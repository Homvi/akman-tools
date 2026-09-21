from __future__ import annotations

import re

import pandas as pd

CAT_LABELS = ("Cat1", "Cat2", "Cat3", "Cat4", "Cat5")
THICK_MM2 = 16.0

_SPECIAL_THIN = re.compile(
    r"(?i)simplex|quadro|cat\.|patch|coax|rg\s?\d|om4|g50/125|os2|"
    r"\bfo\b|belden|aircell|lmr|radar|heiz|leermodule|beistellung|"
    r"seatex|sea\s*tex|draka|0x0"
)
_K_CLASS = re.compile(r"\bK([1-5])\b", re.IGNORECASE)
_TRIPLE = re.compile(r"(?i)(\d+)x(\d+)x(\d+(?:[.,]\d+)?)")
_CORES_X_SIZE = re.compile(r"(?i)\d+[Gx](\d+(?:[.,]\d+)?)")


def extract_k_category(kabel_raw) -> str:
    """Map CaTra suffix K1–K5 to Cat1–Cat5."""
    if kabel_raw is None or (isinstance(kabel_raw, float) and pd.isna(kabel_raw)):
        return "Unclassified"
    match = _K_CLASS.search(str(kabel_raw))
    if not match:
        return "Unclassified"
    return f"Cat{match.group(1)}"


def conductor_mm2(adern) -> float | None:
    if adern is None or (isinstance(adern, float) and pd.isna(adern)):
        return None
    text = str(adern).strip()
    if not text:
        return None
    if _SPECIAL_THIN.search(text):
        return 0.0

    compact = text.replace(" ", "")
    triple = _TRIPLE.search(compact)
    if triple:
        return _to_float(triple.group(3))

    cores = _CORES_X_SIZE.search(compact)
    if cores:
        return _to_float(cores.group(1))
    return None


def thickness_label(adern) -> str:
    mm2 = conductor_mm2(adern)
    if mm2 is None:
        return "Unknown"
    if mm2 >= THICK_MM2:
        return "Thick"
    return "Thin"


def _to_float(token: str) -> float:
    return float(token.replace(",", "."))
