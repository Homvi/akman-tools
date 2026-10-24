from __future__ import annotations

import pandas as pd
import pytest

from apps.api.services import cable_filter as filt


def _frame():
    return pd.DataFrame(
        [
            {
                "Kabelnr": "1",
                "Geraet_A": "CabA",
                "Geraet_E": "Other",
                "Pfad": "1E2104 (E 1,0) 1EDV606 (E 1,0) X1",
                "Pull_status": "Not pulled",
                "Thickness": "thick",
                "Category": "HV",
                "Length_m": 10,
                "Anschluss 1": None,
                "Anschluss 2": None,
                "verlegt": None,
                "Startsegment_1": "1E2104",
                "Endsegment_1": "1EDV606",
                "Startsegment_2": "",
                "Endsegment_2": "",
            },
            {
                "Kabelnr": "2",
                "Geraet_A": "CabB",
                "Geraet_E": "CabA",
                "Pfad": "1E2104 (E 1,0) Y1",
                "Pull_status": "Részlegesen",
                "Thickness": "thin",
                "Category": "LV",
                "Length_m": 20,
                "Anschluss 1": "01.08.2026",
                "Anschluss 2": None,
                "verlegt": None,
                "Startsegment_1": "1E2104",
                "Endsegment_1": "Y1",
                "Startsegment_2": "",
                "Endsegment_2": "",
            },
            {
                "Kabelnr": "3",
                "Geraet_A": "CabC",
                "Geraet_E": "Z",
                "Pfad": "Z1 (E 1,0) Z2",
                "Pull_status": "Pulled",
                "Thickness": "thick",
                "Category": "HV",
                "Length_m": 5,
                "Anschluss 1": "01.08.2026",
                "Anschluss 2": "02.08.2026",
                "verlegt": "03.08.2026",
                "Startsegment_1": "",
                "Endsegment_1": "",
                "Startsegment_2": "",
                "Endsegment_2": "",
            },
        ]
    )


def test_requires_at_least_one_filter():
    with pytest.raises(filt.CableFilterError):
        filt.apply_unified_filter(_frame(), statuses=["not_started", "started", "fully_pulled"])
    with pytest.raises(filt.CableFilterError):
        filt.apply_unified_filter(_frame())


def test_nodes_and_device_and():
    result = filt.apply_unified_filter(
        _frame(),
        nodes_text="1E2104",
        mode="OR",
        devices=["CabA"],
        statuses=["not_started", "started", "fully_pulled"],
    )
    ids = set(result["filtered"]["Kabelnr"].astype(str))
    assert ids == {"1", "2"}
    assert result["nodes"] == ["1E2104"]


def test_device_only_and_status_subset():
    result = filt.apply_unified_filter(
        _frame(),
        devices=["CabA"],
        statuses=["not_started"],
    )
    ids = list(result["filtered"]["Kabelnr"].astype(str))
    assert ids == ["1"]


def test_category_and_thickness():
    result = filt.apply_unified_filter(
        _frame(),
        categories=["HV"],
        thickness=["thick"],
        statuses=["not_started", "started", "fully_pulled"],
    )
    ids = set(result["filtered"]["Kabelnr"].astype(str))
    assert ids == {"1", "3"}
