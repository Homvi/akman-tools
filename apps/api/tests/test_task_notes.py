from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.db import Base
from apps.api.services import staffing_db


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_task_notes_add_list_delete_prune(db):
    known = {"t1", "t2"}
    with pytest.raises(staffing_db.StaffingNotFound):
        staffing_db.add_task_note(db, "ghost", "x", author_email="a@x", known_ids=known)
    with pytest.raises(staffing_db.StaffingError):
        staffing_db.add_task_note(db, "t1", "   ", author_email="a@x", known_ids=known)

    first = staffing_db.add_task_note(db, "t1", "Tray ready on deck 3", author_email="a@x", known_ids=known)
    staffing_db.add_task_note(db, "t1", "Second", author_email="b@x", known_ids=known)
    staffing_db.add_task_note(db, "t2", "Other task", author_email="a@x", known_ids=known)

    grouped = staffing_db.notes_by_task(db, ["t1", "t2"])
    assert [n["text"] for n in grouped["t1"]] == ["Second", "Tray ready on deck 3"]
    assert len(grouped["t2"]) == 1

    assert staffing_db.delete_task_note(db, first["id"], user_email="b@x", is_admin=False) is False
    assert staffing_db.delete_task_note(db, first["id"], user_email="b@x", is_admin=True) is True

    assert staffing_db.prune_task_notes(db, ["t1"]) == 1
    assert staffing_db.notes_by_task(db, ["t1", "t2"]) == {"t1": grouped["t1"][:1]}
