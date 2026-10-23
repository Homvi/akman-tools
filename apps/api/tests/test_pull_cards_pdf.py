from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.analysis import PULL_PARTIAL
from src.pull_cards_pdf import build_pull_cards_pdf


def _frame():
    long_path = (
        "DEV_A (E 2,1) 3EDH006 (E 3,0) N3 (E 1,5) N4 (E 3,0) N5 (E 2,0) "
        "N6 (E 1,0) N7 (E 4,0) 1EDV100 (E 1,0) N9 (E 2,5) DEV_E"
    )
    return pd.DataFrame(
        [
            {
                "Kabelnr": "3311.0320.4401.P",
                "Liste": "L10",
                "Category": "Power",
                "Length_m": 48.0,
                "Remaining_m": 10.0,
                "Pull_status": PULL_PARTIAL,
                "Geraet_A": "Cabinet A",
                "Geraet_E": "Cabinet E",
                "Ort_A": "Room A",
                "Ort_E": "Room E",
                "Knoten_A": "DEV_A",
                "Knoten_E": "DEV_E",
                "Aln_A": 0.0,
                "Aln_E": 0.5,
                "Pfad": long_path,
                "Startsegment_1": "DEV_A",
                "Endsegment_1": "N5",
                "Startsegment_2": "",
                "Endsegment_2": "",
                "Startsegment_3": "",
                "Endsegment_3": "",
                "verlegt": None,
                "Bemerkung": "Priority pull — check clearance",
            },
            {
                "Kabelnr": "3500.1042.0001.P",
                "Liste": "L11",
                "Category": "Light",
                "Length_m": 15.0,
                "Remaining_m": 5.0,
                "Pull_status": PULL_PARTIAL,
                "Geraet_A": "Light A",
                "Geraet_E": "Light E",
                "Ort_A": "Deck",
                "Ort_E": "Deck",
                "Knoten_A": "A1",
                "Knoten_E": "A2",
                "Aln_A": 0.3,
                "Aln_E": 0.0,
                "Pfad": "A1 (E 1,0) 2EDH50 (E 2,0) A2",
                "Startsegment_1": "A1",
                "Endsegment_1": "2EDH50",
                "Startsegment_2": "",
                "Endsegment_2": "",
                "Startsegment_3": "",
                "Endsegment_3": "",
                "verlegt": None,
                "Note": "",
            },
        ]
    )


def test_pull_cards_pdf_bytes_and_header():
    data = build_pull_cards_pdf(
        _frame(),
        filter_note="N5; N10 · OR · started",
        printed_at=datetime(2026, 10, 21, 11, 30),
        lang="en",
        highlight_nodes=["N5", "N10"],
    )
    assert isinstance(data, (bytes, bytearray))
    assert data[:4] == b"%PDF"
    assert len(data) > 500


def test_pull_cards_pdf_languages():
    frame = _frame()
    for lang in ("en", "hu", "de"):
        data = build_pull_cards_pdf(frame, filter_note="test filter", lang=lang)
        assert data[:4] == b"%PDF"
        assert len(data) > 400


def test_pull_cards_pdf_empty_frame():
    data = build_pull_cards_pdf(pd.DataFrame(), filter_note="none", lang="en")
    assert data[:4] == b"%PDF"
