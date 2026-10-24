from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.models import WorkerCategory, WorkerNote, WorkerProfile, WorkerRating
from apps.api.services import workforce_board as board_svc
from apps.api.services.person_names import name_identity_key, person_key
from src.staffing_categories import apply_categories

MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_LANGUAGES = 20
_PHOTO_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class WorkerError(ValueError):
    """Invalid worker input (maps to HTTP 400)."""


class WorkerNotFound(LookupError):
    """Unknown worker (maps to HTTP 404)."""


def photos_dir() -> Path:
    return settings.appdata_path / "uploads" / "workers"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _languages(raw: str | None) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return [str(x) for x in data if str(x).strip()] if isinstance(data, list) else []


def normalize_languages(values: list[Any] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        lang = " ".join(str(value or "").split())[:64]
        if not lang or lang.casefold() in seen:
            continue
        seen.add(lang.casefold())
        out.append(lang)
    return out[:MAX_LANGUAGES]


def _get_profile(db: Session, key: str) -> WorkerProfile | None:
    row = db.query(WorkerProfile).filter(WorkerProfile.person_key == key).first()
    if row is not None:
        return row
    for candidate in db.query(WorkerProfile).all():
        if person_key(candidate.person_key) == key:
            candidate.person_key = key
            return candidate
    return None


def _entries_for_key(db: Session, model: type, key: str) -> list[Any]:
    """Ratings/notes matching identity key, including legacy unsorted person_key rows."""
    exact = (
        db.query(model)
        .filter(model.person_key == key)
        .order_by(model.created_at.desc(), model.id.desc())
        .all()
    )
    if exact:
        return exact
    rows = [
        r
        for r in db.query(model).order_by(model.created_at.desc(), model.id.desc()).all()
        if person_key(r.person_key) == key
    ]
    for r in rows:
        r.person_key = key
    return rows


def _task_assignment(task: dict[str, Any], role: str) -> dict[str, Any]:
    return {
        "id": task.get("id"),
        "title": task.get("title"),
        "role": role,
        "start_date": task.get("start_date"),
        "end_date": task.get("end_date"),
        "blocker": bool(task.get("blocker")),
        "blocker_note": task.get("blocker_note") or "",
        "done": bool(task.get("done")),
    }


def _assigned_tasks(board: dict[str, Any], name: str) -> list[dict[str, Any]]:
    """All tasks this person leads, plus the one task they work on (if any)."""
    key = person_key(name)
    led: list[dict[str, Any]] = []
    worker: dict[str, Any] | None = None
    for task in board.get("tasks") or []:
        if person_key(task.get("lead_id") or "") == key:
            led.append(_task_assignment(task, "lead"))
        elif worker is None and any(person_key(w) == key for w in task.get("worker_ids") or []):
            worker = _task_assignment(task, "worker")
    return [*led, *([worker] if worker else [])]


def get_worker_detail(
    db: Session,
    name: str,
    *,
    people: list[dict[str, Any]] | None = None,
    board: dict[str, Any] | None = None,
) -> dict[str, Any]:
    key = person_key(name)
    if not key:
        raise WorkerNotFound(name)
    if people is None:
        frame = board_svc.load_workforce_frame()
        people = board_svc.list_people(frame) if frame is not None else []
    person = next((p for p in people if person_key(p.get("name", "")) == key), None)
    if person is not None:
        from apps.api.services import staffing_db as staffing_svc

        overrides = staffing_svc.category_overrides(db)
        person = apply_categories([person], overrides, key_of=person_key)[0]
        person = staffing_svc.apply_roster_meta(db, [person])[0]
    profile = _get_profile(db, key)
    if person is None and profile is None:
        raise WorkerNotFound(name)

    ratings = _entries_for_key(db, WorkerRating, key)
    notes = _entries_for_key(db, WorkerNote, key)
    average = round(sum(r.stars for r in ratings) / len(ratings), 2) if ratings else None
    display = (person or {}).get("name") or (profile.display_name if profile else "") or name
    assigned = _assigned_tasks(board if board is not None else board_svc.load_board(), display)

    return {
        "name": display,
        "key": key,
        "in_workforce": person is not None,
        "person": person,
        "tasks": assigned,
        "current_task": assigned[0] if assigned else None,
        "profile": {
            "phone": profile.phone if profile else "",
            "address": profile.address if profile else "",
            "languages": _languages(profile.languages_json) if profile else [],
            "has_photo": bool(profile and profile.photo_path and Path(profile.photo_path).exists()),
            "updated_at": _iso(profile.updated_at) if profile else None,
        },
        "rating": {"average": average, "count": len(ratings)},
        "ratings": [
            {
                "id": r.id,
                "stars": r.stars,
                "comment": r.comment,
                "author_email": r.author_email,
                "created_at": _iso(r.created_at),
            }
            for r in ratings
        ],
        "notes": [
            {"id": n.id, "text": n.text, "author_email": n.author_email, "created_at": _iso(n.created_at)}
            for n in notes
        ],
    }


def _ensure_profile(db: Session, name: str) -> WorkerProfile:
    key = person_key(name)
    if not key:
        raise WorkerError("Name is required")
    profile = _get_profile(db, key)
    if profile is None:
        profile = WorkerProfile(person_key=key, display_name=" ".join(name.split()))
        db.add(profile)
    return profile


def update_profile(
    db: Session,
    name: str,
    *,
    phone: str | None = None,
    address: str | None = None,
    languages: list[Any] | None = None,
) -> WorkerProfile:
    profile = _ensure_profile(db, name)
    if phone is not None:
        profile.phone = str(phone).strip()[:64]
    if address is not None:
        profile.address = str(address).strip()[:512]
    if languages is not None:
        profile.languages_json = json.dumps(normalize_languages(languages), ensure_ascii=False)
    db.commit()
    db.refresh(profile)
    return profile


def add_rating(db: Session, name: str, *, stars: int, comment: str, author_email: str) -> WorkerRating:
    key = person_key(name)
    if not key:
        raise WorkerError("Name is required")
    try:
        value = int(stars)
    except (TypeError, ValueError):
        raise WorkerError("Stars must be 1-5") from None
    if not 1 <= value <= 5:
        raise WorkerError("Stars must be 1-5")
    rating = WorkerRating(
        person_key=key,
        stars=value,
        comment=str(comment or "").strip()[:2000],
        author_email=author_email,
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


def add_note(db: Session, name: str, *, text: str, author_email: str) -> WorkerNote:
    key = person_key(name)
    body = str(text or "").strip()[:5000]
    if not key:
        raise WorkerError("Name is required")
    if not body:
        raise WorkerError("Note text is required")
    note = WorkerNote(person_key=key, text=body, author_email=author_email)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def delete_entry(
    db: Session,
    model: type[WorkerRating] | type[WorkerNote],
    entry_id: int,
    *,
    user_email: str,
    is_admin: bool,
) -> bool:
    """Delete a rating/note. Only its author or an admin may delete it."""
    entry = db.get(model, entry_id)
    if entry is None:
        raise WorkerNotFound(str(entry_id))
    if not is_admin and entry.author_email != user_email:
        return False
    db.delete(entry)
    db.commit()
    return True


def _sniff_image(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def save_photo(db: Session, name: str, *, content: bytes, content_type: str | None) -> WorkerProfile:
    if not content:
        raise WorkerError("Empty file")
    if len(content) > MAX_PHOTO_BYTES:
        raise WorkerError("Photo is larger than 5 MB")
    declared = (content_type or "").split(";")[0].strip().lower()
    sniffed = _sniff_image(content)
    if declared not in _PHOTO_TYPES or sniffed != declared:
        raise WorkerError("Only JPEG, PNG or WebP images are allowed")

    profile = _ensure_profile(db, name)
    folder = photos_dir()
    folder.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(profile.person_key.encode("utf-8")).hexdigest()
    target = folder / f"{digest}.{_PHOTO_TYPES[declared]}"
    if profile.photo_path and Path(profile.photo_path) != target:
        Path(profile.photo_path).unlink(missing_ok=True)
    target.write_bytes(content)
    profile.photo_path = str(target)
    db.commit()
    db.refresh(profile)
    return profile


def photo_file(db: Session, name: str) -> tuple[Path, str] | None:
    profile = _get_profile(db, person_key(name))
    if not profile or not profile.photo_path:
        return None
    path = Path(profile.photo_path)
    if not path.exists():
        return None
    media = next((m for m, ext in _PHOTO_TYPES.items() if path.suffix == f".{ext}"), "application/octet-stream")
    return path, media


def delete_photo(db: Session, name: str) -> None:
    profile = _get_profile(db, person_key(name))
    if not profile or not profile.photo_path:
        return
    Path(profile.photo_path).unlink(missing_ok=True)
    profile.photo_path = ""
    db.commit()
