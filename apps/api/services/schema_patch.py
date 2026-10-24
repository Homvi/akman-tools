"""Lightweight additive schema patches for existing Postgres volumes (no Alembic)."""

from __future__ import annotations

from sqlalchemy import inspect, text

from apps.api.db import engine


def ensure_schema_patches() -> None:
    """Add columns that ``create_all`` will not create on an existing table."""
    insp = inspect(engine)
    if not insp.has_table("worker_profiles"):
        return
    cols = {c["name"] for c in insp.get_columns("worker_profiles")}
    if "inactive" in cols:
        return
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE worker_profiles ADD COLUMN inactive BOOLEAN NOT NULL DEFAULT FALSE")
        )
