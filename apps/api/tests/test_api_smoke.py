from __future__ import annotations

import os

import pytest

# Skip if psycopg / DB not available in unit env — mark for docker CI
pytest.importorskip("fastapi")


def test_health_import():
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg://cable:cable_dev_change_me@localhost:5432/cable",
    )
    from apps.api.main import app

    assert app.title.startswith("Cable")
