from pathlib import Path

from apps.api.services.areas_store import load_areas, load_default_areas


def test_bundled_default_areas_load():
    areas = load_default_areas()
    assert len(areas) >= 1
    assert any(a.trays or a.penetrations for a in areas)


def test_load_areas_falls_back_to_default(tmp_path: Path):
    areas, source = load_areas(tmp_path)
    assert source == "default"
    assert len(areas) == len(load_default_areas())


def test_load_areas_prefers_upload(tmp_path: Path):
    datasets = tmp_path / "datasets"
    datasets.mkdir(parents=True)
    (datasets / "areas.json").write_text(
        '[{"key":"x","name":"Only Upload","deck":"","area_ids":"","trays":["1E1"],"penetrations":[]}]',
        encoding="utf-8",
    )
    areas, source = load_areas(tmp_path)
    assert source == "upload"
    assert len(areas) == 1
    assert areas[0].name == "Only Upload"
