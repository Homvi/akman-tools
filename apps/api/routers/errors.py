from __future__ import annotations

import json
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import dataset as ds

router = APIRouter(prefix="/errors", tags=["errors"])


def _report(db: Session) -> dict:
    row = ds.current_dataset(db)
    if not row:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    frame = ds.load_joined(db)
    conflicts = ds.conflicts_frame(frame) if frame is not None else None
    return {
        "only_status": json.loads(row.only_status_json or "[]"),
        "only_catra": json.loads(row.only_catra_json or "[]"),
        "field_conflicts": conflicts.where(conflicts.notna(), None).to_dict(orient="records")
        if conflicts is not None and not conflicts.empty
        else [],
    }


@router.get("/report")
def error_report(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    return _report(db)


@router.get("/export")
def export_errors(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    report = _report(db)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame({"Kabelnr": report["only_status"]}).to_excel(writer, index=False, sheet_name="Only_Progress")
        pd.DataFrame({"Kabel": report["only_catra"]}).to_excel(writer, index=False, sheet_name="Only_Gesamt")
        pd.DataFrame(report["field_conflicts"]).to_excel(writer, index=False, sheet_name="Field_conflicts")
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="hibak.xlsx"'},
    )
