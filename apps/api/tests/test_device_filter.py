from __future__ import annotations

import pandas as pd

from apps.api.services.filters import filter_cables


def test_device_filter_either_end():
    df = pd.DataFrame(
        [
            {
                "Kabelnr": "1",
                "Geraet_A": "CabA",
                "Geraet_E": "Other",
                "Category": "Cat3",
                "Length_m": 10,
                "Liste": "L1",
                "Pull_status": "Not pulled",
            },
            {
                "Kabelnr": "2",
                "Geraet_A": "Other",
                "Geraet_E": "CabA",
                "Category": "Cat3",
                "Length_m": 20,
                "Liste": "L2",
                "Pull_status": "Not pulled",
            },
            {
                "Kabelnr": "3",
                "Geraet_A": "X",
                "Geraet_E": "Y",
                "Category": "Cat3",
                "Length_m": 30,
                "Liste": "L3",
                "Pull_status": "Not pulled",
            },
        ]
    )
    out = filter_cables(df, devices="CabA")
    assert sorted(out["Kabelnr"].astype(str).tolist()) == ["1", "2"]
