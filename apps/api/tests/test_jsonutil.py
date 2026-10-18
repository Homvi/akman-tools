from __future__ import annotations

import json
import math

import pandas as pd

from apps.api.services.filters import paginate
from apps.api.services.jsonutil import records, safe_float, sanitize


def test_sanitize_nan_inf():
    assert sanitize(float("nan")) is None
    assert sanitize(float("inf")) is None
    assert sanitize(1.5) == 1.5
    assert safe_float(float("nan")) == 0.0
    assert safe_float(float("inf"), default=-1) == -1


def test_records_and_paginate_json_safe():
    df = pd.DataFrame(
        {
            "Kabelnr": ["A1", "A2"],
            "Length_m": [10.5, float("nan")],
            "Remaining_m": [float("inf"), 3.0],
        }
    )
    rows = records(df)
    assert rows[1]["Length_m"] is None
    assert rows[0]["Remaining_m"] is None
    payload = paginate(df, page=1, page_size=10)
    json.dumps(payload)  # must not raise
    assert math.isfinite(payload["total"])
