"""DB-backed staffing data: manual worker categories and task notes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from sqlalchemy.orm import Session

from apps.api.models import TaskNote, WorkerCategory
from apps.api.services import workforce_board as board_svc
from apps.api.services.workers import person_key
from src.staffing_categories import apply_categories, is_category

MAX_TASK_NOTE = 5000


class StaffingError(ValueError):
    """Invalid input (HTTP 400)."""


class StaffingNotFound(LookupError):
    """Unknown task / note (HTTP 404)."""


def category_overrides(db: Session) -> dict[str, str]:
    return {row.person_key: row.category for row in db.query(WorkerCategory).all()}


def people_with_categories(db: Session, people: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return apply_categories(people, category_overrides(db), key_of=person_key)


def load_people(db: Session) -> list[dict[str, Any]] | None:
    """Workforce people with categories applied, or None when no Excel is uploaded."""
    frame = board_svc.load_workforce_frame()
    if frame is None:
        return None
    return people_with_categories(db, board_svc.list_people(frame))


def set_category(db: Session, name: str, category: str | None, *, user_email: str) -> None:
    key = person_key(name)
    if not key:
        raise StaffingError("Name is required")
    row = db.query(WorkerCategory).filter(WorkerCategory.person_key == key).first()
    if category in (None, ""):
        if row is not None:
            db.delete(row)
            db.commit()
        return
    if not is_category(category):
        raise StaffingError("Unknown category")
    if row is None:
        row = WorkerCategory(person_key=key, category=category, updated_by=user_email)
        db.add(row)
    else:
        row.category = category
        row.updated_by = user_email
    db.commit()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _note_dict(note: TaskNote) -> dict[str, Any]:
    return {
        "id": note.id,
        "task_id": note.task_id,
        "text": note.text,
        "author_email": note.author_email,
        "created_at": _iso(note.created_at),
    }


def notes_by_task(db: Session, task_ids: Iterable[str]) -> dict[str, list[dict[str, Any]]]:
    ids = [t for t in task_ids if t]
    if not ids:
        return {}
    rows = (
        db.query(TaskNote)
        .filter(TaskNote.task_id.in_(ids))
        .order_by(TaskNote.created_at.desc(), TaskNote.id.desc())
        .all()
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for note in rows:
        out.setdefault(note.task_id, []).append(_note_dict(note))
    return out


def add_task_note(db: Session, task_id: str, text: str, *, author_email: str, known_ids: set[str]) -> dict[str, Any]:
    if task_id not in known_ids:
        raise StaffingNotFound(task_id)
    body = str(text or "").strip()[:MAX_TASK_NOTE]
    if not body:
        raise StaffingError("Note text is required")
    note = TaskNote(task_id=task_id, text=body, author_email=author_email)
    db.add(note)
    db.commit()
    db.refresh(note)
    return _note_dict(note)


def delete_task_note(db: Session, note_id: int, *, user_email: str, is_admin: bool) -> bool:
    note = db.get(TaskNote, note_id)
    if note is None:
        raise StaffingNotFound(str(note_id))
    if not is_admin and note.author_email != user_email:
        return False
    db.delete(note)
    db.commit()
    return True


def prune_task_notes(db: Session, keep_ids: Iterable[str]) -> int:
    """Drop notes of tasks that no longer exist on the board."""
    keep = list(set(keep_ids))
    query = db.query(TaskNote)
    if keep:
        query = query.filter(~TaskNote.task_id.in_(keep))
    removed = query.delete(synchronize_session=False)
    db.commit()
    return int(removed or 0)
