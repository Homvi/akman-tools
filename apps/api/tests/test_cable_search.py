import pandas as pd

from apps.api.services.cable_lookup import (
    find_cable,
    find_cable_rows,
    find_cables,
    parse_cable_ids,
    search_cable_ids,
)
from src.stutzen_filter import DEFAULT_EXPORT_COLUMNS, select_export_columns


def test_search_cable_ids_typeahead():
    df = pd.DataFrame({"Kabelnr": ["0230", "0231", "1230", "0061", "9999"]})
    assert search_cable_ids(df, "023")[:2] == ["0230", "0231"]
    assert "1230" in search_cable_ids(df, "023")
    assert "1230" in search_cable_ids(df, "230")
    assert search_cable_ids(df, "") == []
    assert search_cable_ids(df, "zzz") == []


def test_search_prefers_prefix():
    df = pd.DataFrame({"Kabelnr": ["120", "0120", "1120"]})
    hits = search_cable_ids(df, "12")
    assert hits[0] in {"120", "0120"}


def test_parse_cable_ids_keeps_comma_in_id():
    assert parse_cable_ids("2114,1") == ["2114,1"]
    assert parse_cable_ids("2114.1") == ["2114,1"]
    assert parse_cable_ids("2114,1; 0006") == ["2114,1", "0006"]
    assert parse_cable_ids("2114,1\n0006") == ["2114,1", "0006"]
    # Space alone is NOT a separator — use semicolon between IDs.
    assert parse_cable_ids("2114,1 0006") == ["2114,1 0006"]
    # Must NOT split a single sub-id on the comma
    assert parse_cable_ids("5012,1;5012,2") == ["5012,1", "5012,2"]
    assert parse_cable_ids("5077,2") == ["5077,2"]
    assert parse_cable_ids("5077, 2") == ["5077,2"]
    assert parse_cable_ids("5077,2;5012,1") == ["5077,2", "5012,1"]
    # Comma-only list without semicolon stays one token
    assert parse_cable_ids("5077,2,5012") == ["5077,2,5012"]


def test_find_cable_matches_comma_and_dot_forms():
    df = pd.DataFrame(
        {
            "Kabelnr": ["2114,1", "0006"],
            "join_key": ["2114,1", "6"],
            "Pfad": ["A (E 1,0) B", "A (E 1,0) B"],
            "Length_m": [10.0, 20.0],
            "Pull_status": ["Not pulled", "Not pulled"],
        }
    )
    row = find_cable(df, "2114,1")
    assert row is not None
    assert str(row["Kabelnr"]) == "2114,1"
    row_dot = find_cable(df, "2114.1")
    assert row_dot is not None
    assert str(row_dot["Kabelnr"]) == "2114,1"

    found, missing = find_cables(df, parse_cable_ids("2114,1; 9999"))
    assert len(found) == 1
    assert found[0]["kabelnr"] == "2114,1"
    assert missing == ["9999"]


def test_find_cable_rows_preserves_order_for_export():
    df = pd.DataFrame(
        {
            "Kabelnr": ["0006", "2114,1"],
            "Liste": ["A", "B"],
            "Category": ["HV", "LV"],
            "Length_m": [20.0, 10.0],
            "Geraet_A": ["GA", "GB"],
            "Geraet_E": ["EA", "EB"],
            "Ort_A": ["OA", "OB"],
            "Ort_E": ["OE", "OF"],
            "verlegt": [None, None],
            "Pfad": ["A (E 1,0) B", "A (E 1,0) B"],
            "Pull_status": ["Not pulled", "Not pulled"],
        }
    )
    rows, missing = find_cable_rows(df, ["2114,1", "0006", "missing"])
    assert missing == ["missing"]
    assert list(rows["Kabelnr"].astype(str)) == ["2114,1", "0006"]
    slim = select_export_columns(rows, list(DEFAULT_EXPORT_COLUMNS))
    assert "Kabelnr" in slim.columns
    assert len(slim) == 2
