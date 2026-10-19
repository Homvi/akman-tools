from __future__ import annotations

from io import BytesIO

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import dataset as ds
from apps.api.services.cable_lookup import find_cable, parse_cable_ids
from src.length_calc import highlight_pulled_segment, stichmass_from_stuetze_to_a
from src.stutzen_filter import cable_route

router = APIRouter(prefix="/stichmass", tags=["stichmass"])


class StichmassBody(BaseModel):
    stuetze: str
    ids: str | list[str] = Field(default="")


def _text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "<na>", "none", "nat"} else text


def _num(value) -> float:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        text = _text(value).replace(",", ".")
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0


def _calc_rows(frame: pd.DataFrame, stuetze: str, ids: list[str]) -> list[dict]:
    results: list[dict] = []
    for kabelnr in ids:
        row = find_cable(frame, kabelnr)
        if row is None:
            results.append(
                {
                    "kabelnr": kabelnr,
                    "ok": False,
                    "error": "Kabel nem található",
                    "liste": "",
                    "node_a": "",
                    "aln_a": 0.0,
                    "meters": None,
                    "route_m": None,
                    "allowance_a": None,
                    "route_html": "",
                    "route": "",
                }
            )
            continue

        route = cable_route(row)
        node_a = _text(row.get("Knoten_A")) or _text(row.get("Point_A"))
        aln_a = _num(row.get("Aln_A"))
        liste = _text(row.get("Liste"))
        result = stichmass_from_stuetze_to_a(route, stuetze, node_a, aln_a)
        if not result.ok:
            results.append(
                {
                    "kabelnr": kabelnr,
                    "ok": False,
                    "error": result.error or "Stütze nem található a nyomvonalon",
                    "liste": liste,
                    "node_a": node_a,
                    "aln_a": aln_a,
                    "meters": None,
                    "route_m": None,
                    "allowance_a": None,
                    "route_html": highlight_pulled_segment(route, "", "") if route else "",
                    "route": route,
                }
            )
            continue

        results.append(
            {
                "kabelnr": kabelnr,
                "ok": True,
                "error": "",
                "liste": liste,
                "node_a": node_a,
                "aln_a": aln_a,
                "meters": round(result.meters, 1),
                "route_m": round(result.route_m, 1),
                "allowance_a": round(result.allowance_a, 1),
                "route_html": highlight_pulled_segment(route, stuetze, node_a),
                "route": route,
            }
        )
    return results


@router.post("/calc")
def stichmass_calc(
    body: StichmassBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin", "worker")),
):
    stuetze = str(body.stuetze or "").strip()
    if not stuetze:
        raise HTTPException(status_code=400, detail="Stütze megadása kötelező")
    ids = parse_cable_ids(body.ids)
    if not ids:
        raise HTTPException(status_code=400, detail="Legalább egy Kabelnr kell")
    frame = ds.load_joined(db)
    if frame is None or frame.empty:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    rows = _calc_rows(frame, stuetze, ids)
    return {"stuetze": stuetze, "ids": ids, "rows": rows}


@router.post("/export")
def stichmass_export(
    body: StichmassBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin", "worker")),
):
    stuetze = str(body.stuetze or "").strip()
    if not stuetze:
        raise HTTPException(status_code=400, detail="Stütze megadása kötelező")
    ids = parse_cable_ids(body.ids)
    if not ids:
        raise HTTPException(status_code=400, detail="Legalább egy Kabelnr kell")
    frame = ds.load_joined(db)
    if frame is None or frame.empty:
        raise HTTPException(status_code=404, detail="No dataset loaded")
    rows = _calc_rows(frame, stuetze, ids)
    export_df = pd.DataFrame(
        [
            {
                "Kabelnr": r["kabelnr"],
                "Liste": r["liste"],
                "A": r["node_a"],
                "Aln_A": r["aln_a"],
                "Stichmaß_m": r["meters"] if r["ok"] else "",
                "Route_m": r["route_m"] if r["ok"] else "",
                "Hiba": "" if r["ok"] else r["error"],
            }
            for r in rows
        ]
    )
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="E-Stichmass")
    fname = f"e_stichmass_{stuetze.replace(' ', '_')}.xlsx"
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
