from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.db import Base
from apps.api.services import staffing_db
from src.staffing_categories import (
    apply_categories,
    guess_category,
    normalize_requirements,
    requirements_summary,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_guess_category_from_excel_positions():
    assert guess_category("Cable puller") == "cable_puller"
    assert guess_category("  electric ") == "electrician"
    assert guess_category("Electrician") == "electrician"
    assert guess_category("Cable pull team leader") == "long_distance_lead"
    assert guess_category("Engineer") == "engineer"
    assert guess_category("Mérnök") == "engineer"
    assert guess_category("Warehouse manager") == "warehouse_manager"
    assert guess_category("Wharehouse manager") == "warehouse_manager"
    assert guess_category("Lakatos csoportvezető") == "iron_worker_lead"
    assert guess_category("Iron worker") == "iron_worker"
    assert guess_category("Lakatos") == "iron_worker"
    assert guess_category("Site Manager") == "site_manager"
    assert guess_category("Építésvezető") == "site_manager"
    assert guess_category("Office") == "administration"
    assert guess_category("Team lead") is None
    assert guess_category(None) is None


def test_manual_override_wins_and_survives_new_people_list(db):
    people = [
        {"id": "Anna", "name": "Anna", "position": "Cable puller", "is_lead": False},
        {"id": "Béla", "name": "Béla", "position": "Team lead", "is_lead": True},
        {"id": "Cili", "name": "Cili", "position": "Helper", "is_lead": False},
    ]
    staffing_db.set_category(db, "anna", "local_cabling_lead", user_email="p@x")
    staffing_db.set_category(db, "Béla", "electrician_lead", user_email="p@x")
    with pytest.raises(staffing_db.StaffingError):
        staffing_db.set_category(db, "Cili", "astronaut", user_email="p@x")

    # A fresh Excel upload produces the same names again → overrides still apply.
    by = {p["name"]: p for p in staffing_db.people_with_categories(db, people)}
    assert by["Anna"]["category"] == "local_cabling_lead"
    assert by["Anna"]["category_source"] == "manual"
    assert by["Anna"]["is_lead"] is True
    assert by["Béla"]["category"] == "electrician_lead"
    assert by["Cili"]["category"] is None and by["Cili"]["category_source"] is None

    staffing_db.set_category(db, "Anna", None, user_email="p@x")
    anna = staffing_db.people_with_categories(db, people)[0]
    assert anna["category"] == "cable_puller"
    assert anna["category_source"] == "auto"
    assert anna["is_lead"] is False


def test_roster_meta_afternoon_and_project_survives_people_reload(db):
    people = [
        {"id": "Anna", "name": "Anna", "position": "Cable puller", "is_lead": False},
        {"id": "Béla", "name": "Béla", "position": "Electrician", "is_lead": False},
    ]
    meta = staffing_db.set_roster_meta(
        db, "anna", afternoon=True, project="598", user_email="p@x"
    )
    assert meta == {"afternoon": True, "project": "598"}
    with pytest.raises(staffing_db.StaffingError):
        staffing_db.set_roster_meta(db, "Béla", afternoon=False, project="999", user_email="p@x")

    by = {p["name"]: p for p in staffing_db.people_with_categories(db, people)}
    assert by["Anna"]["afternoon"] is True
    assert by["Anna"]["project"] == "598"
    assert by["Béla"]["afternoon"] is False
    assert by["Béla"]["project"] is None

    cleared = staffing_db.set_roster_meta(
        db, "Anna", afternoon=False, project=None, user_email="p@x"
    )
    assert cleared == {"afternoon": False, "project": None}
    anna = staffing_db.people_with_categories(db, people)[0]
    assert anna["afternoon"] is False
    assert anna["project"] is None


def test_people_with_categories_hides_inactive_profiles(db):
    from apps.api.services import workers as worker_svc

    people = [
        {"id": "Anna", "name": "Anna", "position": "Cable puller", "is_lead": False},
        {"id": "Béla", "name": "Béla", "position": "Electrician", "is_lead": False},
    ]
    worker_svc.update_profile(db, "Anna", inactive=True)
    names = {p["name"] for p in staffing_db.people_with_categories(db, people)}
    assert names == {"Béla"}


def test_roster_meta_legacy_unsorted_key_still_applies(db):
    """Old DB rows used casefold-without-sort; identity key must still find them."""
    from apps.api.models import WorkerRosterMeta

    db.add(
        WorkerRosterMeta(
            person_key="brewka patryk daniel",
            afternoon=True,
            project="598",
            updated_by="legacy@x",
        )
    )
    db.commit()
    people = [
        {
            "id": "Patryk Daniel Brewka",
            "name": "Patryk Daniel Brewka",
            "position": "Cable puller",
            "is_lead": False,
        }
    ]
    by = {p["name"]: p for p in staffing_db.people_with_categories(db, people)}
    assert by["Patryk Daniel Brewka"]["afternoon"] is True
    assert by["Patryk Daniel Brewka"]["project"] == "598"


def test_normalize_requirements():
    assert normalize_requirements({"cable_puller": "3", "bogus": 5, "electrician": 0, "electrician_lead": 500}) == {
        "cable_puller": 3,
        "electrician_lead": 99,
    }
    assert normalize_requirements(None) == {}


def test_requirements_summary():
    people = apply_categories(
        [
            {"id": "A", "name": "A", "position": "Cable puller"},
            {"id": "B", "name": "B", "position": "Cable puller", "on_leave": True},
            {"id": "C", "name": "C", "position": "Cable pull team leader",
             "leave_ranges": [{"start": "2026-10-28", "end": "2026-10-29"}]},
        ],
        {},
    )
    tasks = [
        {"requirements": {"cable_puller": 2, "long_distance_lead": 1}, "lead_id": "C", "worker_ids": ["A"]},
        {"requirements": {"cable_puller": 1}, "worker_ids": []},
        {"requirements": {"cable_puller": 5}, "done": True, "worker_ids": ["B"]},
    ]
    rows = {r["category"]: r for r in requirements_summary(tasks, people, today=date(2026, 10, 24))}
    puller = rows["cable_puller"]
    assert (puller["needed"], puller["roster"], puller["assigned"], puller["short"]) == (3, 2, 1, True)
    assert puller["on_leave_now"] == 1
    lead = rows["long_distance_lead"]
    assert (lead["needed"], lead["roster"], lead["leave_next_week"], lead["short"]) == (1, 1, 1, False)
    assert rows["electrician"]["needed"] == 0
