import pandas as pd

from apps.api.services.cable_lookup import search_cable_ids


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
