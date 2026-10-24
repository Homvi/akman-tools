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
from apps.api.services.workforce_board import clear_workforce_cache
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
    project: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("planner", "admin")),
):
    """Upload headcount Excel.

    Without ``project``: replaces the main (untagged) roster slice.
    With ``project`` (e.g. ``600``): replaces that ship slice and defaults
    those people to the given project on the organisation roster.
    """
    proj = (project or "").strip() or None
    if proj and proj not in staffing_db.PROJECTS:
        raise HTTPException(status_code=400, detail="Unknown project")

    upload_name = f"workforce_{proj}.xlsx" if proj else "workforce.xlsx"
    path = settings.appdata_path / "uploads" / upload_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(await file.read())
    try:
        incoming = parse_workforce_excel(path, year=year, project=proj)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing = board_svc.load_workforce_frame()
    merged = board_svc.merge_workforce_upload(existing, incoming, project=proj)
    out = settings.appdata_path / "datasets" / _WF_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(out, index=False)
    clear_workforce_cache()

    project_updated = 0
    project_598 = 0
    if proj == "600" and "Name" in incoming.columns:
        # Only October sheet names become project 600; everyone else defaults to 598.
        try:
            roster_names = (
                merged["Name"].dropna().astype(str).tolist()
                if merged is not None and not merged.empty and "Name" in merged.columns
                else []
            )
            counts = staffing_db.apply_ship_600_project_defaults(
                db,
                incoming=incoming,
                roster_names=roster_names,
                user_email=user.email,
            )
            project_updated = int(counts.get("project_600", 0))
            project_598 = int(counts.get("project_598", 0))
        except staffing_db.StaffingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
    elif proj and "Name" in incoming.columns:
        try:
            project_updated = staffing_db.apply_default_project(
                db,
                incoming["Name"].dropna().astype(str).tolist(),
                project=proj,
                user_email=user.email,
            )
        except staffing_db.StaffingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    people_in_upload = int(incoming["Name"].nunique()) if "Name" in incoming.columns else 0
    october_people = (
        len(staffing_db.names_on_sheet(incoming, "October")) if proj == "600" else 0
    )
    return {
        "ok": True,
        "rows": len(merged),
        "upload_rows": len(incoming),
        "people": people_in_upload if proj != "600" else october_people,
        "project": proj,
        "project_updated": project_updated,
        "project_598_updated": project_598,
    }


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


class RosterBody(BaseModel):
    name: str
    afternoon: bool = False
    project: str | None = None


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
    off_roster = staffing_db.load_off_roster(db)
    as_of = next((p.get("as_of") for p in people if p.get("as_of")), None)
    if as_of is None and off_roster:
        as_of = next((p.get("as_of") for p in off_roster if p.get("as_of")), None)
    on_leave = sum(1 for p in people if p.get("on_leave"))
    roster_month = None
    next_month = None
    if as_of:
        try:
            day = date.fromisoformat(str(as_of)[:10])
            current, nxt = board_svc.roster_months(day)
            roster_month = f"{current.year}-{current.month:02d}"
            next_month = f"{nxt.year}-{nxt.month:02d}"
        except ValueError:
            pass
    return {
        "people": people,
        "off_roster": off_roster,
        "positions": board_svc.unique_positions_from_people(people),
        "categories": list(CATEGORIES),
        "projects": sorted(staffing_db.PROJECTS),
        "count": len(people),
        "as_of": as_of,
        "roster_month": roster_month,
        "next_month": next_month,
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


@router.put("/people/roster")
def put_person_roster(
    body: RosterBody,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("planner", "admin")),
):
    try:
        meta = staffing_db.set_roster_meta(
            db,
            body.name,
            afternoon=body.afternoon,
            project=body.project,
            user_email=user.email,
        )
    except staffing_db.StaffingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {"name": body.name, **meta}


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
