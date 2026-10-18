from __future__ import annotations

import pandas as pd

from apps.api.services.device_stats import (
    AT_DEVICE,
    NOT_STARTED,
    STARTED,
    cable_device_progress,
    device_pull_stats,
    filter_by_device_progress,
)


def _row(**kwargs):
    base = {
        "Startsegment_1": "",
        "Endsegment_1": "",
        "Startsegment_2": "",
        "Endsegment_2": "",
        "Startsegment_3": "",
        "Endsegment_3": "",
        "verlegt": None,
    }
    base.update(kwargs)
    return pd.Series(base)


def test_three_buckets_for_device_side():
    at = _row(
        Geraet_A="CabA",
        Geraet_E="Other",
        Knoten_A="N1",
        Knoten_E="N3",
        Pfad="N1 (E 1,0) N2 (E 1,0) N3",
        Startsegment_1="N1",
        Endsegment_1="N2",
    )
    assert cable_device_progress(at, "CabA") == AT_DEVICE

    started = _row(
        Geraet_A="CabA",
        Geraet_E="Other",
        Knoten_A="N1",
        Knoten_E="N3",
        Pfad="N1 (E 1,0) N2 (E 1,0) N3",
        Startsegment_1="N2",
        Endsegment_1="N3",
    )
    assert cable_device_progress(started, "CabA") == STARTED
    assert cable_device_progress(started, "Other") == AT_DEVICE

    idle = _row(
        Geraet_A="CabA",
        Geraet_E="Other",
        Knoten_A="N1",
        Knoten_E="N3",
        Pfad="N1 (E 1,0) N3",
    )
    assert cable_device_progress(idle, "CabA") == NOT_STARTED


def test_verlegt_is_at_device():
    row = _row(
        Geraet_A="CabA",
        Geraet_E="CabB",
        Knoten_A="N1",
        Knoten_E="N2",
        Pfad="N1 (E 1,0) N2",
        verlegt="01.09.2026",
    )
    assert cable_device_progress(row, "CabA") == AT_DEVICE
    assert cable_device_progress(row, "CabB") == AT_DEVICE


def test_device_pull_stats_counts():
    df = pd.DataFrame(
        [
            {
                "Kabelnr": "1",
                "Geraet_A": "CabA",
                "Geraet_E": "X",
                "Knoten_A": "A1",
                "Knoten_E": "X1",
                "Pfad": "A1 (E 1,0) X1",
                "verlegt": "01.09.2026",
                "Startsegment_1": "",
                "Endsegment_1": "",
                "Startsegment_2": "",
                "Endsegment_2": "",
                "Startsegment_3": "",
                "Endsegment_3": "",
            },
            {
                "Kabelnr": "2",
                "Geraet_A": "Y",
                "Geraet_E": "CabA",
                "Knoten_A": "Y1",
                "Knoten_E": "A2",
                "Pfad": "Y1 (E 1,0) M1 (E 1,0) A2",
                "verlegt": None,
                "Startsegment_1": "Y1",
                "Endsegment_1": "M1",
                "Startsegment_2": "",
                "Endsegment_2": "",
                "Startsegment_3": "",
                "Endsegment_3": "",
            },
            {
                "Kabelnr": "3",
                "Geraet_A": "CabA",
                "Geraet_E": "Z",
                "Knoten_A": "A3",
                "Knoten_E": "Z1",
                "Pfad": "A3 (E 1,0) Z1",
                "verlegt": None,
                "Startsegment_1": "",
                "Endsegment_1": "",
                "Startsegment_2": "",
                "Endsegment_2": "",
                "Startsegment_3": "",
                "Endsegment_3": "",
            },
        ]
    )
    stats = device_pull_stats(df, "CabA")
    assert stats["device_cables"] == 3
    assert stats["device_at"] == 1
    assert stats["device_started"] == 1
    assert stats["device_not_started"] == 1
    started_only = filter_by_device_progress(df, "CabA", "started")
    assert list(started_only["Kabelnr"].astype(str)) == ["2"]
