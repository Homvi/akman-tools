from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User
from apps.api.services import dataset as ds
from apps.api.services import staffing_db
from apps.api.services import workforce_board as board_svc
from apps.api.services.jsonutil import records
from apps.api.services.workers import person_key
from src.progress import build_pull_events, daily_progress
from src.staffing_categories import CATEGORIES
from src.task_board_pdf import build_task_board_pdf
from src.workforce import (
    daily_headcount,
    daily_hours,
    headcount_growth,
    meters_per_hour,
    meters_per_person,
    parse_workforce_excel,
)

router = APIRouter(prefix="/workforce", tags=["workforce"])

_WF_PATH = "workforce.parquet"


class BoardBody(BaseModel):
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    # Legacy fields accepted so old clients don't 422; normalize_board migrates/ignores them.
    teams: list[dict[str, Any]] = Field(default_factory=list)
    assignments: dict[str, str | None] = Field(default_factory=dict)


@router.post("/upload")
async def upload_workforce(
    file: UploadFile = File(...),
    year: int = 2026,
    _: User = Depends(require_roles("planner", "admin")),
):
    path = settings.appdata_path / "uploads" / "workforce.xlsx"
    path.write_bytes(await file.read())
    try:
        frame = parse_workforce_excel(path, year=year)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    out = settings.appdata_path / "datasets" / _WF_PATH
    frame.to_parquet(out, index=False)
    return {"ok": True, "rows": len(frame), "people": int(frame["Name"].nunique()) if "Name" in frame.columns else 0}


@router.get("/series")
def workforce_series(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    path = settings.appdata_path / "datasets" / _WF_PATH
    if not path.exists():
        raise HTTPException(status_code=404, detail="No workforce data")
    import pandas as pd

    wf = pd.read_parquet(path)
    daily_hc = daily_headcount(wf)
    hours = daily_hours(wf)
    growth = headcount_growth(daily_hc)
    meters_daily = None
    joined = ds.load_joined(db)
    if joined is not None and not joined.empty:
        events = build_pull_events(joined)
        meters_daily = daily_progress(events)
    m_person = meters_per_person(daily_hc, meters_daily) if meters_daily is not None else None
    m_hour = meters_per_hour(hours, meters_daily) if meters_daily is not None else None
    return {
        "headcount": records(daily_hc),
        "hours": records(hours),
        "growth": growth,
        "m_per_person": records(m_person) if m_person is not None else [],
        "m_per_hour": records(m_hour) if m_hour is not None else [],
    }


class CategoryBody(BaseModel):
    name: str
    category: str | None = None


class TaskNoteBody(BaseModel):
    text: str


def _is_admin(user: User) -> bool:
    return any(r.name == "admin" for r in user.roles)


@router.get("/people")
def workforce_people(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin", "worker")),
):
    people = staffing_db.load_people(db)
    if people is None:
        raise HTTPException(status_code=404, detail="No workforce data — upload the headcount Excel first")
    as_of = next((p.get("as_of") for p in people if p.get("as_of")), None)
    on_leave = sum(1 for p in people if p.get("on_leave"))
    return {
        "people": people,
        "positions": board_svc.unique_positions_from_people(people),
        "categories": list(CATEGORIES),
        "count": len(people),
        "as_of": as_of,
        "on_leave_count": on_leave,
        "available_count": len(people) - on_leave,
    }


@router.put("/people/category")
def put_person_category(
    body: CategoryBody,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("planner", "admin")),
):
    try:
        staffing_db.set_category(db, body.name, body.category, user_email=user.email)
    except staffing_db.StaffingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    people = staffing_db.load_people(db) or []
    key = person_key(body.name)
    person = next((p for p in people if person_key(p.get("name", "")) == key), None)
    return {"name": body.name, "category": person.get("category") if person else body.category,
            "category_source": person.get("category_source") if person else None}


@router.get("/leave-missing")
def leave_missing(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin", "worker")),
):
    people = staffing_db.load_people(db)
    if not people:
        return {"as_of": None, "count": 0, "people": []}
    missing = [
        {"name": p["name"], "position": p.get("position") or "", "category": p.get("category")}
        for p in people
        if not p.get("leave_ranges") and not p.get("on_leave")
    ]
    missing.sort(key=lambda p: (p["category"] is None, p["category"] or "", p["name"].casefold()))
    return {"as_of": people[0].get("as_of"), "count": len(missing), "people": missing}


@router.get("/board")
def get_workforce_board(
    _: User = Depends(require_roles("planner", "admin", "worker")),
):
    return board_svc.load_board()


@router.put("/board")
def put_workforce_board(
    body: BoardBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    board = board_svc.save_board(body.model_dump())
    staffing_db.prune_task_notes(db, [t["id"] for t in board["tasks"]])
    return board


@router.get("/board/pdf")
def board_pdf(
    lang: str = "hu",
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin")),
):
    board = board_svc.load_board()
    people = staffing_db.load_people(db) or []
    notes = staffing_db.notes_by_task(db, [t["id"] for t in board["tasks"]])
    pdf = build_task_board_pdf(board, people, notes, lang=lang)
    filename = f"csapatok_{date.today().isoformat()}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/board/notes")
def get_task_notes(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("planner", "admin", "worker")),
):
    ids = [t["id"] for t in board_svc.load_board()["tasks"]]
    return staffing_db.notes_by_task(db, ids)


@router.post("/tasks/{task_id}/notes")
def post_task_note(
    task_id: str,
    body: TaskNoteBody,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("planner", "admin")),
):
    known = {t["id"] for t in board_svc.load_board()["tasks"]}
    try:
        return staffing_db.add_task_note(db, task_id, body.text, author_email=user.email, known_ids=known)
    except staffing_db.StaffingNotFound:
        raise HTTPException(status_code=404, detail="Task not found") from None
    except staffing_db.StaffingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.delete("/tasks/notes/{note_id}")
def delete_task_note(
    note_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("planner", "admin")),
):
    try:
        allowed = staffing_db.delete_task_note(db, note_id, user_email=user.email, is_admin=_is_admin(user))
    except staffing_db.StaffingNotFound:
        raise HTTPException(status_code=404, detail="Note not found") from None
    if not allowed:
        raise HTTPException(status_code=403, detail="Only the author or an admin can delete this")
    return {"ok": True}
