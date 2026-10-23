from __future__ import annotations

import pandas as pd

from apps.api.services.priority_devices import (
    PRIORITY_DEVICE_NAMES,
    device_priority_stats,
    priority_export_frame,
)
from src.stutzen_filter import select_export_columns


def _frame():
    return pd.DataFrame(
        [
            {
                "Kabelnr": "1",
                "Geraet_A": "CabA",
                "Geraet_E": "Other",
                "Knoten_A": "A1",
                "Knoten_E": "X1",
                "Pfad": "A1 (E 1,0) X1",
                "Anschluss 1": "01.08.2026",
                "Anschluss 2": None,
                "verlegt": None,
                "Startsegment_1": "A1",
                "Endsegment_1": "X1",
                "Startsegment_2": "",
                "Endsegment_2": "",
                "Startsegment_3": "",
                "Endsegment_3": "",
                "Pull_status": "Részlegesen",
                "Liste": "L1",
                "Category": "Cat",
                "Length_m": 10,
            },
            {
                "Kabelnr": "2",
                "Geraet_A": "Y",
                "Geraet_E": "CabA",
                "Knoten_A": "Y1",
                "Knoten_E": "A2",
                "Pfad": "Y1 (E 1,0) M1 (E 1,0) A2",
                "Anschluss 1": None,
                "Anschluss 2": "02.08.2026",
                "verlegt": None,
                "Startsegment_1": "Y1",
                "Endsegment_1": "M1",
                "Startsegment_2": "",
                "Endsegment_2": "",
                "Startsegment_3": "",
                "Endsegment_3": "",
                "Pull_status": "Részlegesen",
                "Liste": "L1",
                "Category": "Cat",
                "Length_m": 20,
            },
            {
                "Kabelnr": "3",
                "Geraet_A": "CabA",
                "Geraet_E": "Z",
                "Knoten_A": "A3",
                "Knoten_E": "Z1",
                "Pfad": "A3 (E 1,0) Z1",
                "Anschluss 1": None,
                "Anschluss 2": None,
                "verlegt": None,
                "Startsegment_1": "",
                "Endsegment_1": "",
                "Startsegment_2": "",
                "Endsegment_2": "",
                "Startsegment_3": "",
                "Endsegment_3": "",
                "Pull_status": "Not pulled",
                "Liste": "L1",
                "Category": "Cat",
                "Length_m": 5,
            },
            {
                "Kabelnr": "4",
                "Geraet_A": "Elsewhere",
                "Geraet_E": "Also",
                "Knoten_A": "E1",
                "Knoten_E": "E2",
                "Pfad": "E1 (E 1,0) E2",
                "Anschluss 1": "01.08.2026",
                "Anschluss 2": "01.08.2026",
                "verlegt": "01.09.2026",
                "Startsegment_1": "",
                "Endsegment_1": "",
                "Startsegment_2": "",
                "Endsegment_2": "",
                "Startsegment_3": "",
                "Endsegment_3": "",
                "Pull_status": "Pulled",
                "Liste": "L1",
                "Category": "Cat",
                "Length_m": 8,
            },
        ]
    )


def test_priority_stats_wired_and_pulled_by_side():
    stats = device_priority_stats(_frame(), "CabA")
    assert stats["matched"] is True
    assert stats["total"] == 3
    # Cable1: A side wired+pulled; Cable2: E side wired, started not at A2; Cable3: A idle
    assert stats["wired_a"] == 1
    assert stats["wired_e"] == 1
    assert stats["wired"] == 2
    assert stats["pulled_a"] == 1
    assert stats["pulled_e"] == 0
    assert stats["pulled"] == 1
    assert stats["device_at"] == 1
    assert stats["device_started"] == 1
    assert stats["device_not_started"] == 1


def test_priority_stats_unmatched_name():
    stats = device_priority_stats(_frame(), "Missing Device")
    assert stats["matched"] is False
    assert stats["total"] == 0


def test_priority_export_status_and_columns():
    df = _frame()
    started = priority_export_frame(df, devices=["CabA"], statuses=["started"])
    assert set(started["Kabelnr"].astype(str)) == {"1", "2"}
    not_started = priority_export_frame(df, devices=["CabA"], statuses=["not_started"])
    assert list(not_started["Kabelnr"].astype(str)) == ["3"]
    both = priority_export_frame(df, devices=["CabA"], statuses=["started", "not_started"])
    assert set(both["Kabelnr"].astype(str)) == {"1", "2", "3"}
    slim = select_export_columns(both, ["kabelnr", "liste", "geraet_a", "geraet_e"])
    assert list(slim.columns) == ["Kabelnr", "Liste", "Geraet_A", "Geraet_E"]


def test_priority_list_constant_order():
    assert PRIORITY_DEVICE_NAMES[0] == "44b AMS Cabinet 1 Bow"
    assert PRIORITY_DEVICE_NAMES[3] == "2 Main Switchboard Bow"
    assert PRIORITY_DEVICE_NAMES[-1] == "8 Main Distribution 24V DC Mid"
    assert len(PRIORITY_DEVICE_NAMES) == 20
    assert "DBL" not in PRIORITY_DEVICE_NAMES
