from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.models import Dataset
from apps.api.services.jsonutil import safe_float
from src.analysis import PULL_NOT, PULL_PARTIAL, PULL_YES, assign_pull_status
from src.dates import is_pulled, series_to_dates
from src.export import catra_list_xlsx, kurzliste_xlsx, to_xlsx_bytes
from src.join import join_cable_data, unmatched_ids
from src.parsers import parse_catra_list, parse_status_list
from src.reconcile import enrich_joined_for_reconcile, field_mismatches

_PROGRESS_DATE_COLS = ("verlegt", "Gestoppt_1", "Gestoppt_2", "Gestoppt_3")


def _norm_col(name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else " " for ch in str(name)).split()


def _find_col(df: pd.DataFrame, *tokens: str) -> str | None:
    """Find a column whose normalized words match tokens (e.g. anschluss, 1)."""
    want = [t.lower() for t in tokens]
    for col in df.columns:
        parts = _norm_col(col)
        if parts == want:
            return str(col)
    # softer: all tokens present in order
    for col in df.columns:
        parts = _norm_col(col)
        if all(t in parts for t in want):
            return str(col)
    return None


def _has_date_series(series: pd.Series) -> pd.Series:
    return series.map(lambda v: bool(is_pulled(v)) if v is not None else False)


def _signature(status_bytes: bytes, catra_bytes: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(status_bytes)
    digest.update(catra_bytes)
    return digest.hexdigest()


def current_dataset(db: Session) -> Dataset | None:
    return db.query(Dataset).order_by(Dataset.id.desc()).first()


def load_joined(db: Session) -> pd.DataFrame | None:
    ds = current_dataset(db)
    if not ds or not ds.parquet_path:
        return None
    path = Path(ds.parquet_path)
    if not path.exists():
        return None
    return pd.read_parquet(path)


def progress_as_of(df: pd.DataFrame | None) -> dict:
    """Latest date across Progressliste event columns (verlegt + Gestoppt_*)."""
    empty = {"progress_as_of": None, "progress_as_of_iso": None}
    if df is None or df.empty:
        return empty
    stamps: list[pd.Timestamp] = []
    for col in _PROGRESS_DATE_COLS:
        if col not in df.columns:
            continue
        series = series_to_dates(df[col])
        valid = series.dropna()
        if not valid.empty:
            stamps.append(pd.Timestamp(valid.max()))
    if not stamps:
        return empty
    latest = max(stamps)
    if pd.isna(latest):
        return empty
    ts = latest.normalize()
    return {
        "progress_as_of": ts.strftime("%d.%m.%Y"),
        "progress_as_of_iso": ts.date().isoformat(),
    }


def length_summary(df: pd.DataFrame | None) -> dict:
    """Catalogue total + fully/partially pulled + not-started meters."""
    zero = {
        "total_length_m": 0.0,
        "fully_pulled_m": 0.0,
        "partially_pulled_m": 0.0,
        "not_started_m": 0.0,
        "pulled_total_m": 0.0,
        "cable_count": 0,
    }
    if df is None or df.empty:
        return zero
    frame = assign_pull_status(df)
    total = safe_float(frame["Length_m"].fillna(0).sum()) if "Length_m" in frame.columns else 0.0
    fully = 0.0
    not_started = 0.0
    if "Length_m" in frame.columns and "Pull_status" in frame.columns:
        fully = safe_float(frame.loc[frame["Pull_status"] == PULL_YES, "Length_m"].fillna(0).sum())
        not_started = safe_float(frame.loc[frame["Pull_status"] == PULL_NOT, "Length_m"].fillna(0).sum())
    partial = 0.0
    if "Total_teilgezogene_meter" in frame.columns and "Pull_status" in frame.columns:
        partial = safe_float(
            frame.loc[frame["Pull_status"] == PULL_PARTIAL, "Total_teilgezogene_meter"].fillna(0).sum()
        )
    return {
        "total_length_m": total,
        "fully_pulled_m": fully,
        "partially_pulled_m": partial,
        "not_started_m": not_started,
        "pulled_total_m": safe_float(fully + partial),
        "cable_count": int(len(frame)),
    }


def wired_not_verlegt(df: pd.DataFrame | None) -> list[str]:
    """Kabelnr with Anschluss on BOTH ends and no verlegt (legacy helper)."""
    items = anschluss_without_verlegt(df)
    return [row["kabelnr"] for row in items if set(row.get("sides") or []) >= {"A", "E"}]


def anschluss_without_verlegt(df: pd.DataFrame | None) -> list[dict]:
    """
    Cables with Anschluss 1 (A / kezdőpont) and/or Anschluss 2 (E / végpont)
    dated, but no verlegt (not handed over yet).

    Returns [{"kabelnr": "1234", "sides": ["A"], "started": False}, ...] sorted by kabelnr.
    `started` is True if any Startsegment / partial pull exists (Pull_status != Not pulled).
    """
    if df is None or df.empty or "Kabelnr" not in df.columns:
        return []
    # Accept raw Excel headers ("Anschluss 1") and normalized ("Anschluss_1").
    col_a = (
        _find_col(df, "anschluss", "1")
        or ("Anschluss_1" if "Anschluss_1" in df.columns else None)
        or ("Anschluss 1" if "Anschluss 1" in df.columns else None)
    )
    col_e = (
        _find_col(df, "anschluss", "2")
        or ("Anschluss_2" if "Anschluss_2" in df.columns else None)
        or ("Anschluss 2" if "Anschluss 2" in df.columns else None)
    )
    if not col_a and not col_e:
        return []
    frame = assign_pull_status(df)
    if "verlegt" in frame.columns:
        no_verlegt = ~_has_date_series(frame["verlegt"])
    else:
        no_verlegt = pd.Series(True, index=frame.index)
    has_a = _has_date_series(frame[col_a]) if col_a else pd.Series(False, index=frame.index)
    has_e = _has_date_series(frame[col_e]) if col_e else pd.Series(False, index=frame.index)
    mask = no_verlegt & (has_a | has_e)
    out: list[dict] = []
    for idx in frame.index[mask]:
        kabelnr = str(frame.at[idx, "Kabelnr"]).strip()
        if not kabelnr or kabelnr.lower() in {"nan", "<na>", "none"}:
            continue
        sides: list[str] = []
        if bool(has_a.at[idx]):
            sides.append("A")
        if bool(has_e.at[idx]):
            sides.append("E")
        if not sides:
            continue
        status = str(frame.at[idx, "Pull_status"] or "")
        started = status != PULL_NOT
        out.append({"kabelnr": kabelnr, "sides": sides, "started": started})
    out.sort(key=lambda row: (len(row["kabelnr"]), row["kabelnr"]))
    return out


def dataset_payload(db: Session, row: Dataset | None = None) -> dict:
    row = row or current_dataset(db)
    if not row:
        return {"loaded": False, **progress_as_of(None), **length_summary(None)}
    frame = load_joined(db)
    dates = progress_as_of(frame)
    return {
        "loaded": True,
        "status_name": row.status_name,
        "catra_name": row.catra_name,
        "signature": row.signature,
        "cable_count": row.cable_count,
        "only_status": json.loads(row.only_status_json or "[]"),
        "only_catra": json.loads(row.only_catra_json or "[]"),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        **dates,
    }


def save_joined_dataset(
    db: Session,
    *,
    joined: pd.DataFrame,
    status_name: str,
    catra_name: str,
    signature: str,
    header: list,
    only_status: list,
    only_catra: list,
) -> Dataset:
    out_dir = settings.appdata_path / "datasets"
    parquet_path = out_dir / "joined.parquet"
    # Drop heavy object columns that don't serialize well
    frame = joined.copy()
    drop = [c for c in frame.columns if c.startswith("_") and c not in ("_liste_progress", "_liste_gesamt")]
    if "_block" in frame.columns:
        drop.append("_block")
    frame = frame.drop(columns=list(dict.fromkeys(drop)), errors="ignore")
    for col in frame.columns:
        if frame[col].dtype == object:
            frame[col] = frame[col].astype("string")
    frame.to_parquet(parquet_path, index=False)

    db.query(Dataset).delete()
    ds = Dataset(
        status_name=status_name,
        catra_name=catra_name,
        signature=signature,
        cable_count=len(joined),
        parquet_path=str(parquet_path),
        header_json=json.dumps(header, default=str),
        only_status_json=json.dumps(only_status, default=str),
        only_catra_json=json.dumps(only_catra, default=str),
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


def ingest_uploads(
    db: Session,
    *,
    status_file,
    catra_file=None,
) -> Dataset:
    """Ingest Progressliste (+ optional Gesamtliste). Reuses last catra.xlsx if omitted."""
    status_bytes = status_file.file.read()
    status_path = settings.appdata_path / "uploads" / "status.xlsx"
    catra_path = settings.appdata_path / "uploads" / "catra.xlsx"
    status_path.write_bytes(status_bytes)

    existing = current_dataset(db)
    if catra_file is not None:
        catra_bytes = catra_file.file.read()
        catra_path.write_bytes(catra_bytes)
        catra_name = catra_file.filename or "Gesamtliste"
    else:
        if not catra_path.exists():
            raise ValueError("Gesamtliste required for the first upload")
        catra_bytes = catra_path.read_bytes()
        catra_name = (existing.catra_name if existing else None) or "Gesamtliste"

    status = parse_status_list(status_path)
    catra = parse_catra_list(catra_path)
    joined = join_cable_data(status, catra)
    joined = enrich_joined_for_reconcile(status, catra, joined)
    only_status, only_catra = unmatched_ids(status, catra)
    header = list(catra.attrs.get("catra_header") or [])
    sig = _signature(status_bytes, catra_bytes)
    return save_joined_dataset(
        db,
        joined=joined,
        status_name=status_file.filename or "Progressliste",
        catra_name=catra_name,
        signature=sig,
        header=header,
        only_status=only_status,
        only_catra=only_catra,
    )


def conflicts_frame(joined: pd.DataFrame) -> pd.DataFrame:
    return field_mismatches(joined)


def export_catra(df: pd.DataFrame, header: list | None = None) -> bytes:
    return catra_list_xlsx(df, header)


def export_kurzliste(df: pd.DataFrame) -> bytes:
    return kurzliste_xlsx(df)


def export_table(df: pd.DataFrame, sheet: str = "Data") -> bytes:
    return to_xlsx_bytes(df, sheet_name=sheet)
