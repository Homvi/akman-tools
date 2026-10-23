from __future__ import annotations

import pandas as pd

from apps.api.services.cable_lookup import cable_detail, find_cable
from apps.api.services.dataset import (
    anschluss_without_verlegt,
    length_summary,
    progress_as_of,
    wired_not_verlegt,
)


def test_progress_as_of_max_date():
    df = pd.DataFrame(
        {
            "verlegt": ["01.08.2026", None, None],
            "Gestoppt_1": [None, "15.09.2026", None],
            "Gestoppt_2": [None, None, "01.09.2026"],
            "Gestoppt_3": [None, None, None],
        }
    )
    result = progress_as_of(df)
    assert result["progress_as_of"] == "15.09.2026"
    assert result["progress_as_of_iso"] == "2026-09-15"


def test_length_summary_split():
    df = pd.DataFrame(
        {
            "Length_m": [100.0, 50.0, 40.0],
            "Total_teilgezogene_meter": [0.0, 20.0, 0.0],
            "Pulled": [True, False, False],
            "Startsegment_1": ["", "A1", ""],
            "Pull_status": ["Pulled", "Részlegesen", "Not pulled"],
        }
    )
    summary = length_summary(df)
    assert summary["total_length_m"] == 190.0
    assert summary["fully_pulled_m"] == 100.0
    assert summary["partially_pulled_m"] == 20.0
    assert summary["not_started_m"] == 40.0
    assert summary["pulled_total_m"] == 120.0


def test_cable_lookup_highlight():
    df = pd.DataFrame(
        [
            {
                "Kabelnr": "1234",
                "Pfad": "A1 (E 1,0) B2 (E 2,0) C3",
                "verlegt": None,
                "Pulled": False,
                "Pull_status": "Részlegesen",
                "Startsegment_1": "A1",
                "Endsegment_1": "B2",
                "Startsegment_2": "",
                "Endsegment_2": "",
                "Startsegment_3": "",
                "Endsegment_3": "",
                "Gestoppt_1": "01.09.2026",
                "Length_m": 10.0,
                "Category": "Cat3",
                "Liste": "001",
                "Artikel": "Ship Data Cat.7",
                "Typ": "Quadro",
                "Geraet_A": "DevA",
                "Geraet_E": "DevE",
                "Ort_A": "3D #33",
                "Ort_E": "1D #66",
                "Aln_A": "5.5",
                "Aln_E": "6",
            }
        ]
    )
    row = find_cable(df, "1234")
    assert row is not None
    detail = cable_detail(row)
    assert detail["status"] == "partial"
    assert "01.09.2026" in detail["status_message"]
    assert detail["cable_type"] == "Ship Data Cat.7"
    assert detail["adern"] == "Quadro"
    assert detail["aln_a"] == "5.5"
    assert detail["geraet_a"] == "DevA"
    assert "mark" in detail["route_html"]
    assert detail["pulled_start"] == "A1"
    assert detail["pulled_end"] == "B2"


def test_wired_not_verlegt_both_anschluss():
    df = pd.DataFrame(
        [
            {
                "Kabelnr": "100",
                "Anschluss 1": "01.08.2026",
                "Anschluss 2": "02.08.2026",
                "verlegt": None,
            },
            {
                "Kabelnr": "200",
                "Anschluss 1": "01.08.2026",
                "Anschluss 2": None,
                "verlegt": None,
            },
            {
                "Kabelnr": "300",
                "Anschluss 1": "01.08.2026",
                "Anschluss 2": "02.08.2026",
                "verlegt": "10.08.2026",
            },
            {
                "Kabelnr": "400",
                "Anschluss 1": None,
                "Anschluss 2": "03.08.2026",
                "verlegt": None,
            },
        ]
    )
    assert wired_not_verlegt(df) == ["100"]
    open_rows = anschluss_without_verlegt(df)
    assert open_rows == [
        {"kabelnr": "100", "sides": ["A", "E"], "started": False},
        {"kabelnr": "200", "sides": ["A"], "started": False},
        {"kabelnr": "400", "sides": ["E"], "started": False},
    ]


def test_anschluss_underscore_headers():
    df = pd.DataFrame(
        [
            {"Kabelnr": "0230", "Anschluss_1": "10.09.2026", "Anschluss_2": None, "verlegt": None},
            {"Kabelnr": "0231", "Anschluss_1": None, "Anschluss_2": "11.09.2026", "verlegt": pd.NaT},
        ]
    )
    assert anschluss_without_verlegt(df) == [
        {"kabelnr": "0230", "sides": ["A"], "started": False},
        {"kabelnr": "0231", "sides": ["E"], "started": False},
    ]


def test_anschluss_started_vs_not_started():
    df = pd.DataFrame(
        [
            {
                "Kabelnr": "10",
                "Anschluss 1": "01.08.2026",
                "Anschluss 2": None,
                "verlegt": None,
                "Startsegment_1": "1EDV100",
            },
            {
                "Kabelnr": "20",
                "Anschluss 1": "01.08.2026",
                "Anschluss 2": "02.08.2026",
                "verlegt": None,
            },
        ]
    )
    rows = {r["kabelnr"]: r for r in anschluss_without_verlegt(df)}
    assert rows["10"]["started"] is True
    assert rows["20"]["started"] is False


def test_cable_complete_shows_verlegt_date():
    df = pd.DataFrame(
        [
            {
                "Kabelnr": "9999",
                "Pfad": "X1 (E 1,0) Y2",
                "verlegt": "12.08.2026",
                "Pulled": True,
                "Length_m": 20.0,
                "Kabeltyp": "TypeA",
                "Kabeladern": "2x2.5",
            }
        ]
    )
    detail = cable_detail(find_cable(df, "9999"))
    assert detail["status"] == "complete"
    assert detail["verlegt_date"] == "12.08.2026"
    assert detail["status_message"] == "Behúzva: 12.08.2026"
    assert "Teljesen leadva" not in detail["status_message"]
    assert detail["route_missing"] is False
    assert detail["route_warning"] == ""


def test_cable_complete_missing_pfad_no_nan_feedback():
    df = pd.DataFrame(
        [
            {
                "Kabelnr": "4012",
                "Pfad": float("nan"),
                "verlegt": "29.08.2026",
                "Pulled": True,
                "Length_m": 46.0,
                "Liste": "0020",
                "Geraet_A": "61 Schottel Switchboard PU1",
                "Geraet_E": "137 Schottel Drive Motor PU 1",
            }
        ]
    )
    detail = cable_detail(find_cable(df, "4012"))
    assert detail["status"] == "complete"
    assert detail["verlegt_date"] == "29.08.2026"
    assert detail["route_missing"] is True
    assert "Pfad" in detail["route_warning"]
    assert detail["route"] == ""
    assert detail["route_html"] == ""
    assert detail["pulled_start"] == ""
    assert detail["pulled_end"] == ""
    assert detail["nodes"] == []
    assert "nan" not in detail["status_message"].lower()
    assert "Pfad" in detail["status_message"]
    assert detail["status_label"] == "Teljesen behúzva"


def test_cable_complete_string_nan_pfad_treated_as_missing():
    df = pd.DataFrame(
        [
            {
                "Kabelnr": "4013",
                "Pfad": "nan",
                "verlegt": "01.09.2026",
                "Length_m": 10.0,
            }
        ]
    )
    detail = cable_detail(find_cable(df, "4013"))
    assert detail["status"] == "complete"
    assert detail["route_missing"] is True
    assert detail["pulled_start"] == ""
    assert "nan" not in (detail.get("route") or "").lower()
