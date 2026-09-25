from __future__ import annotations

import pickle
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "cables.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dataset (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            joined BLOB NOT NULL,
            header BLOB,
            only_status BLOB,
            only_catra BLOB,
            status_name TEXT,
            catra_name TEXT,
            signature TEXT,
            saved_at TEXT
        )
        """
    )
    return conn


def save_dataset(
    *,
    joined,
    header,
    only_status,
    only_catra,
    status_name: str,
    catra_name: str,
    signature: str,
) -> None:
    payload = (
        pickle.dumps(joined, protocol=pickle.HIGHEST_PROTOCOL),
        pickle.dumps(header, protocol=pickle.HIGHEST_PROTOCOL),
        pickle.dumps(only_status, protocol=pickle.HIGHEST_PROTOCOL),
        pickle.dumps(only_catra, protocol=pickle.HIGHEST_PROTOCOL),
        status_name,
        catra_name,
        signature,
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    with _connect() as conn:
        conn.execute("DELETE FROM dataset")
        conn.execute(
            """
            INSERT INTO dataset (
                id, joined, header, only_status, only_catra,
                status_name, catra_name, signature, saved_at
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )


def load_dataset() -> dict | None:
    if not DB_PATH.exists():
        return None
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT joined, header, only_status, only_catra,
                   status_name, catra_name, signature, saved_at
            FROM dataset WHERE id = 1
            """
        ).fetchone()
    if not row:
        return None
    return {
        "joined": pickle.loads(row[0]),
        "header": pickle.loads(row[1]) if row[1] else [],
        "only_status": pickle.loads(row[2]) if row[2] else [],
        "only_catra": pickle.loads(row[3]) if row[3] else [],
        "status_name": row[4],
        "catra_name": row[5],
        "signature": row[6],
        "saved_at": row[7],
    }


def clear_dataset() -> None:
    if DB_PATH.exists():
        with _connect() as conn:
            conn.execute("DELETE FROM dataset")


def _ensure_workforce_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workforce (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            frame BLOB NOT NULL,
            file_name TEXT,
            signature TEXT,
            year INTEGER,
            saved_at TEXT
        )
        """
    )


def save_workforce(*, frame, file_name: str, signature: str, year: int) -> None:
    payload = (
        pickle.dumps(frame, protocol=pickle.HIGHEST_PROTOCOL),
        file_name,
        signature,
        int(year),
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    with _connect() as conn:
        _ensure_workforce_table(conn)
        conn.execute("DELETE FROM workforce")
        conn.execute(
            """
            INSERT INTO workforce (id, frame, file_name, signature, year, saved_at)
            VALUES (1, ?, ?, ?, ?, ?)
            """,
            payload,
        )


def load_workforce() -> dict | None:
    if not DB_PATH.exists():
        return None
    with _connect() as conn:
        _ensure_workforce_table(conn)
        row = conn.execute(
            """
            SELECT frame, file_name, signature, year, saved_at
            FROM workforce WHERE id = 1
            """
        ).fetchone()
    if not row:
        return None
    return {
        "frame": pickle.loads(row[0]),
        "file_name": row[1],
        "signature": row[2],
        "year": row[3],
        "saved_at": row[4],
    }


def clear_workforce() -> None:
    if not DB_PATH.exists():
        return
    with _connect() as conn:
        _ensure_workforce_table(conn)
        conn.execute("DELETE FROM workforce")
