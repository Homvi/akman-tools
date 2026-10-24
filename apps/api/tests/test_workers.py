from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.db import Base
from apps.api.models import WorkerNote, WorkerRating
from apps.api.services import workers as svc

PEOPLE = [
    {
        "id": "Kovács Anna",
        "name": "Kovács Anna",
        "position": "Team lead",
        "is_lead": True,
        "on_leave": False,
        "leave_ranges": [{"start": "2026-11-02", "end": "2026-11-06"}],
    }
]
BOARD = {
    "tasks": [
        {"id": "t1", "title": "Deck 3", "lead_id": None, "worker_ids": ["Béla"]},
        {
            "id": "t2",
            "title": "HV feeders",
            "lead_id": "Kovács Anna",
            "worker_ids": [],
            "start_date": "2026-10-27",
            "end_date": "2026-11-14",
            "blocker": True,
            "blocker_note": "tray missing",
        },
        {"id": "t3", "title": "Pull 4012", "lead_id": "Kovács Anna", "worker_ids": ["Cecil"]},
    ]
}


@pytest.fixture()
def db(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(svc, "photos_dir", lambda: tmp_path / "workers")
    yield session
    session.close()


def detail(db, name="Kovács Anna"):
    return svc.get_worker_detail(db, name, people=PEOPLE, board=BOARD)


def test_person_key_order_case_and_accents():
    assert svc.person_key("Brewka Patryk Daniel") == svc.person_key("Patryk Daniel Brewka")
    assert svc.person_key("Brewka Patryk Daniel") == svc.person_key("patryk daniel BREWKA")
    assert svc.person_key("Kovács Anna") == svc.person_key("Anna Kovacs")
    assert svc.person_key("Kovács Anna") == svc.person_key("  kovács   ANNA ")
    # Different token counts stay distinct.
    assert svc.person_key("Brewka Patryk") != svc.person_key("Brewka Patryk Daniel")
    assert svc.person_key("") == ""
    assert svc.person_key("   ") == ""


def test_detail_merges_workforce_and_current_task(db):
    d = detail(db, "  kovács   ANNA ")
    assert d["name"] == "Kovács Anna"
    assert d["in_workforce"] is True
    assert d["person"]["leave_ranges"][0]["start"] == "2026-11-02"
    assert d["current_task"]["title"] == "HV feeders"
    assert d["current_task"]["role"] == "lead"
    assert d["current_task"]["blocker_note"] == "tray missing"
    assert [t["title"] for t in d["tasks"]] == ["HV feeders", "Pull 4012"]
    assert {t["role"] for t in d["tasks"]} == {"lead"}
    assert d["rating"] == {"average": None, "count": 0}


def test_unknown_worker_raises(db):
    with pytest.raises(svc.WorkerNotFound):
        svc.get_worker_detail(db, "Nobody", people=PEOPLE, board=BOARD)


def test_profile_upsert_and_language_normalization(db):
    svc.update_profile(db, "Kovács Anna", phone=" +36 30 123 4567 ", languages=[" magyar", "Magyar", "angol ", ""])
    svc.update_profile(db, "Kovács Anna", address="Budapest, Fő utca 1.")
    profile = detail(db)["profile"]
    assert profile["phone"] == "+36 30 123 4567"
    assert profile["address"] == "Budapest, Fő utca 1."
    assert profile["languages"] == ["magyar", "angol"]


def test_ratings_range_average_and_author_delete(db):
    with pytest.raises(svc.WorkerError):
        svc.add_rating(db, "Kovács Anna", stars=6, comment="", author_email="a@x")
    first = svc.add_rating(db, "Kovács Anna", stars=5, comment="great", author_email="a@x")
    svc.add_rating(db, "Kovács Anna", stars=4, comment="", author_email="b@x")
    d = detail(db)
    assert d["rating"] == {"average": 4.5, "count": 2}
    assert d["ratings"][0]["stars"] == 4

    assert svc.delete_entry(db, WorkerRating, first.id, user_email="b@x", is_admin=False) is False
    assert svc.delete_entry(db, WorkerRating, first.id, user_email="a@x", is_admin=False) is True
    assert detail(db)["rating"]["count"] == 1


def test_notes_add_and_delete(db):
    with pytest.raises(svc.WorkerError):
        svc.add_note(db, "Kovács Anna", text="   ", author_email="a@x")
    note = svc.add_note(db, "Kovács Anna", text="Has a forklift licence", author_email="a@x")
    assert detail(db)["notes"][0]["text"] == "Has a forklift licence"
    assert svc.delete_entry(db, WorkerNote, note.id, user_email="other@x", is_admin=True) is True
    assert detail(db)["notes"] == []


def test_photo_validation_and_replace(db, tmp_path):
    with pytest.raises(svc.WorkerError):
        svc.save_photo(db, "Kovács Anna", content=b"GIF89a....", content_type="image/png")
    with pytest.raises(svc.WorkerError):
        # declared JPEG but bytes are PNG
        svc.save_photo(db, "Kovács Anna", content=b"\x89PNG\r\n\x1a\nxxxx", content_type="image/jpeg")

    svc.save_photo(db, "Kovács Anna", content=b"\x89PNG\r\n\x1a\nxxxx", content_type="image/png")
    assert detail(db)["profile"]["has_photo"] is True
    svc.save_photo(db, "Kovács Anna", content=b"\xff\xd8\xff\xe0jpeg", content_type="image/jpeg")
    files = sorted(p.suffix for p in (tmp_path / "workers").iterdir())
    assert files == [".jpg"]
    path, media = svc.photo_file(db, "Kovács Anna")
    assert media == "image/jpeg"

    svc.delete_photo(db, "Kovács Anna")
    assert detail(db)["profile"]["has_photo"] is False
    assert not path.exists()
