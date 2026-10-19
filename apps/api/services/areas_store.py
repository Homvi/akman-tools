from __future__ import annotations

import json
from pathlib import Path

from src.areas import AreaDef, parse_areas_excel

_AREAS_JSON = "areas.json"
_DEFAULTS_DIR = Path(__file__).resolve().parents[1] / "defaults"
_DEFAULT_JSON = _DEFAULTS_DIR / "areas.json"
_DEFAULT_XLSX = _DEFAULTS_DIR / "helyseg_adatok.xlsx"


def default_areas_paths() -> tuple[Path, Path]:
    return _DEFAULT_JSON, _DEFAULT_XLSX


def _from_payload(raw) -> list[AreaDef]:
    if not isinstance(raw, list):
        return []
    return [AreaDef(**item) for item in raw]


def load_default_areas() -> list[AreaDef]:
    """Bundled Helység adatok — used when nothing newer was uploaded."""
    if _DEFAULT_JSON.exists():
        return _from_payload(json.loads(_DEFAULT_JSON.read_text(encoding="utf-8")))
    if _DEFAULT_XLSX.exists():
        return parse_areas_excel(_DEFAULT_XLSX)
    return []


def load_areas(appdata: Path) -> tuple[list[AreaDef], str]:
    """
    Prefer uploaded datasets/areas.json; fall back to bundled defaults.

    Returns (areas, source) where source is \"upload\" | \"default\" | \"empty\".
    """
    uploaded = appdata / "datasets" / _AREAS_JSON
    if uploaded.exists():
        try:
            areas = _from_payload(json.loads(uploaded.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError, ValueError):
            areas = []
        if areas:
            return areas, "upload"
    defaults = load_default_areas()
    if defaults:
        return defaults, "default"
    return [], "empty"


def areas_to_payload(areas: list[AreaDef]) -> list[dict]:
    return [
        {
            "key": a.key,
            "name": a.name,
            "deck": a.deck,
            "area_ids": a.area_ids,
            "trays": a.trays,
            "penetrations": a.penetrations,
        }
        for a in areas
    ]
