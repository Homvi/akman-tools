from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.db import get_db
from apps.api.deps import require_roles
from apps.api.models import User, WorkerNote, WorkerRating
from apps.api.services import workers as svc

router = APIRouter(prefix="/workers", tags=["workers"])

_staff = require_roles("planner", "admin")


class ProfileBody(BaseModel):
    phone: str | None = None
    address: str | None = None
    languages: list[str] | None = None


class RatingBody(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: str = ""


class NoteBody(BaseModel):
    text: str


def _is_admin(user: User) -> bool:
    return any(r.name == "admin" for r in user.roles)


def _detail(db: Session, name: str):
    try:
        return svc.get_worker_detail(db, name)
    except svc.WorkerNotFound:
        raise HTTPException(status_code=404, detail="Worker not found") from None


@router.get("/profile")
def get_profile(
    name: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    _: User = Depends(_staff),
):
    return _detail(db, name)


@router.put("/profile")
def put_profile(
    body: ProfileBody,
    name: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    _: User = Depends(_staff),
):
    try:
        svc.update_profile(db, name, phone=body.phone, address=body.address, languages=body.languages)
    except svc.WorkerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _detail(db, name)


@router.post("/ratings")
def post_rating(
    body: RatingBody,
    name: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: User = Depends(_staff),
):
    try:
        svc.add_rating(db, name, stars=body.stars, comment=body.comment, author_email=user.email)
    except svc.WorkerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _detail(db, name)


@router.post("/notes")
def post_note(
    body: NoteBody,
    name: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: User = Depends(_staff),
):
    try:
        svc.add_note(db, name, text=body.text, author_email=user.email)
    except svc.WorkerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _detail(db, name)


def _delete(db: Session, model, entry_id: int, user: User) -> None:
    try:
        allowed = svc.delete_entry(db, model, entry_id, user_email=user.email, is_admin=_is_admin(user))
    except svc.WorkerNotFound:
        raise HTTPException(status_code=404, detail="Entry not found") from None
    if not allowed:
        raise HTTPException(status_code=403, detail="Only the author or an admin can delete this")


@router.delete("/ratings/{entry_id}")
def delete_rating(
    entry_id: int,
    name: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: User = Depends(_staff),
):
    _delete(db, WorkerRating, entry_id, user)
    return _detail(db, name)


@router.delete("/notes/{entry_id}")
def delete_note(
    entry_id: int,
    name: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: User = Depends(_staff),
):
    _delete(db, WorkerNote, entry_id, user)
    return _detail(db, name)


@router.post("/photo")
async def post_photo(
    name: str = Query(..., min_length=1),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(_staff),
):
    content = await file.read(svc.MAX_PHOTO_BYTES + 1)
    try:
        svc.save_photo(db, name, content=content, content_type=file.content_type)
    except svc.WorkerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _detail(db, name)


@router.get("/photo")
def get_photo(
    name: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    _: User = Depends(_staff),
):
    found = svc.photo_file(db, name)
    if not found:
        raise HTTPException(status_code=404, detail="No photo")
    path, media = found
    return FileResponse(path, media_type=media, headers={"Cache-Control": "private, max-age=300"})


@router.delete("/photo")
def delete_photo(
    name: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    _: User = Depends(_staff),
):
    svc.delete_photo(db, name)
    return _detail(db, name)
