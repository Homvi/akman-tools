from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd

from apps.api.services import live_progressliste as live_pl
from src.analysis import PULL_PARTIAL, near_complete_cables


def _patch_paths(tmp_path: Path, monkeypatch):
    uploads = tmp_path / "uploads"
    datasets = tmp_path / "datasets"
    uploads.mkdir(parents=True)
    datasets.mkdir(parents=True)
    monkeypatch.setattr(live_pl, "_upload_path", lambda: uploads / "live_progressliste.xlsx")
    monkeypatch.setattr(live_pl, "_parquet_path", lambda: datasets / "live_progressliste.parquet")
    monkeypatch.setattr(live_pl, "_meta_path", lambda: datasets / "live_progressliste_meta.json")


def _xlsx(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def test_save_and_verlegt_keys(tmp_path: Path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)

    df = pd.DataFrame(
        {
            "Kabelnr": ["1001", "1002", "1003"],
            "verlegt": ["01.09.2026", None, "15.09.2026"],
        }
    )
    meta = live_pl.save_live_progressliste(_xlsx(df), file_name="live.xlsx")
    assert meta["loaded"] is True
    assert meta["cable_count"] == 3
    assert meta["verlegt_count"] == 2
    assert meta["file_name"] == "live.xlsx"

    keys = live_pl.load_live_verlegt_keys()
    assert "1001" in keys
    assert "1003" in keys
    assert "1002" not in keys

    status = live_pl.status()
    assert status["loaded"] is True
    assert status["verlegt_count"] == 2


def test_exclude_live_verlegt_on_off(tmp_path: Path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)

    live_pl.save_live_progressliste(
        _xlsx(pd.DataFrame({"Kabelnr": ["A", "B"], "verlegt": ["01.09.2026", None]})),
        file_name="ov.xlsx",
    )

    near = pd.DataFrame(
        {
            "Kabelnr": ["A", "B", "C"],
            "Remaining_m": [5.0, 8.0, 3.0],
            "Length_m": [50.0, 40.0, 30.0],
            "Pull_status": [PULL_PARTIAL, PULL_PARTIAL, PULL_PARTIAL],
        }
    )

    off, missing_off = live_pl.exclude_live_verlegt(near, enabled=False)
    assert list(off["Kabelnr"]) == ["A", "B", "C"]
    assert missing_off is False

    on, missing_on = live_pl.exclude_live_verlegt(near, enabled=True)
    assert list(on["Kabelnr"]) == ["B", "C"]
    assert missing_on is False


def test_exclude_missing_overlay(tmp_path: Path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    near = pd.DataFrame({"Kabelnr": ["X"], "Remaining_m": [2.0]})
    out, missing = live_pl.exclude_live_verlegt(near, enabled=True)
    assert list(out["Kabelnr"]) == ["X"]
    assert missing is True


def test_near_complete_then_exclude(tmp_path: Path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)

    live_pl.save_live_progressliste(_xlsx(pd.DataFrame({"Kabelnr": ["a"], "verlegt": ["01.08.2026"]})))

    df = pd.DataFrame(
        {
            "Kabelnr": ["a", "b", "c"],
            "Pull_status": [PULL_PARTIAL, PULL_PARTIAL, PULL_PARTIAL],
            "Remaining_m": [10.0, 15.0, 20.0],
            "Length_m": [100.0, 50.0, 80.0],
        }
    )
    near = near_complete_cables(df, max_remaining_m=15.0)
    assert list(near["Kabelnr"]) == ["a", "b"]
    filtered, _ = live_pl.exclude_live_verlegt(near, enabled=True)
    assert list(filtered["Kabelnr"]) == ["b"]


def test_live_fully_pulled_m(tmp_path: Path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    live_pl.save_live_progressliste(
        _xlsx(pd.DataFrame({"Kabelnr": ["a", "b"], "verlegt": ["01.08.2026", None]}))
    )
    joined = pd.DataFrame(
        {
            "Kabelnr": ["a", "b", "c"],
            "Length_m": [100.0, 50.0, 80.0],
        }
    )
    # Only "a" is verlegt in live → 100 m
    assert round(live_pl.live_fully_pulled_m(joined), 1) == 100.0
    filtered, _ = live_pl.exclude_live_verlegt(
        pd.DataFrame(
            {
                "Kabelnr": ["a", "b"],
                "Length_m": [100.0, 50.0],
                "Remaining_m": [5.0, 8.0],
                "Pull_status": [PULL_PARTIAL, PULL_PARTIAL],
            }
        ),
        enabled=True,
    )
    gain = float(filtered["Length_m"].sum())
    assert round(gain, 1) == 50.0
    assert round(live_pl.live_fully_pulled_m(joined) + gain, 1) == 150.0
