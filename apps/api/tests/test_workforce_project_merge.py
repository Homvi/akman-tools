from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.db import Base
from apps.api.services import staffing_db
from apps.api.services import workforce_board as board_svc
from apps.api.services.workers import person_key
from src.workforce import parse_workforce_excel


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _frame(rows: list[dict], *, project: str | None = None) -> pd.DataFrame:
    out = pd.DataFrame(rows)
    out["Project"] = project
    return out


def test_merge_main_upload_keeps_project_600_rows():
    existing = pd.concat(
        [
            _frame(
                [
                    {
                        "Date": "2026-10-01",
                        "Name": "Main Anna",
                        "Position": "Cable puller",
                        "Present": True,
                        "Hours": 10,
                        "Status": "work",
                        "Sheet": "October",
                    }
                ],
                project=None,
            ),
            _frame(
                [
                    {
                        "Date": "2026-10-01",
                        "Name": "Ship Béla",
                        "Position": "Electrician",
                        "Present": True,
                        "Hours": 10,
                        "Status": "work",
                        "Sheet": "October",
                    }
                ],
                project="600",
            ),
        ],
        ignore_index=True,
    )
    incoming = _frame(
        [
            {
                "Date": "2026-10-02",
                "Name": "Main Cecil",
                "Position": "Cable puller",
                "Present": True,
                "Hours": 8,
                "Status": "work",
                "Sheet": "October",
            }
        ],
        project=None,
    )
    merged = board_svc.merge_workforce_upload(existing, incoming, project=None)
    names = set(merged["Name"])
    assert "Ship Béla" in names
    assert "Main Cecil" in names
    assert "Main Anna" not in names  # replaced main slice
    assert set(merged.loc[merged["Name"] == "Ship Béla", "Project"]) == {"600"}
    assert merged.loc[merged["Name"] == "Main Cecil", "Project"].isna().all()


def test_merge_project_600_upload_keeps_main_rows():
    existing = pd.concat(
        [
            _frame(
                [
                    {
                        "Date": "2026-10-01",
                        "Name": "Main Anna",
                        "Position": "Cable puller",
                        "Present": True,
                        "Hours": 10,
                        "Status": "work",
                        "Sheet": "October",
                    }
                ],
                project=None,
            ),
            _frame(
                [
                    {
                        "Date": "2026-10-01",
                        "Name": "Old 600",
                        "Position": "Helper",
                        "Present": True,
                        "Hours": 10,
                        "Status": "work",
                        "Sheet": "October",
                    }
                ],
                project="600",
            ),
        ],
        ignore_index=True,
    )
    incoming = _frame(
        [
            {
                "Date": "2026-10-05",
                "Name": "New 600",
                "Position": "Cable puller",
                "Present": True,
                "Hours": 10,
                "Status": "work",
                "Sheet": "October",
            }
        ],
        project=None,  # upload stamps project in merge
    )
    merged = board_svc.merge_workforce_upload(existing, incoming, project="600")
    names = set(merged["Name"])
    assert "Main Anna" in names
    assert "New 600" in names
    assert "Old 600" not in names
    assert set(merged.loc[merged["Name"] == "New 600", "Project"]) == {"600"}


def test_apply_default_project_sets_meta(db):
    n = staffing_db.apply_default_project(
        db,
        ["Reynaldo Ramos", "Mimay Gerald", "Reynaldo Ramos"],
        project="600",
        user_email="planner@test.local",
    )
    assert n == 2
    people = [
        {"id": "Reynaldo Ramos", "name": "Reynaldo Ramos", "position": "Cable puller"},
        {"id": "Mimay Gerald", "name": "Mimay Gerald", "position": "Cable puller"},
        {"id": "Other", "name": "Other", "position": "Office"},
    ]
    enriched = staffing_db.apply_roster_meta(db, people)
    by_name = {p["name"]: p for p in enriched}
    assert by_name["Reynaldo Ramos"]["project"] == "600"
    assert by_name["Mimay Gerald"]["project"] == "600"
    assert by_name["Other"]["project"] is None
    # Afternoon untouched (false by default)
    assert by_name["Reynaldo Ramos"]["afternoon"] is False


def test_apply_default_project_keeps_afternoon(db):
    staffing_db.set_roster_meta(
        db, "Anna", afternoon=True, project="598", user_email="a@test"
    )
    staffing_db.apply_default_project(db, ["Anna"], project="600", user_email="b@test")
    meta = staffing_db.apply_roster_meta(db, [{"name": "Anna", "id": "Anna", "position": ""}])[0]
    assert meta["project"] == "600"
    assert meta["afternoon"] is True


def test_ship_600_defaults_only_october_to_600(db):
    incoming = pd.DataFrame(
        [
            {
                "Date": "2026-09-01",
                "Name": "Sept Only",
                "Position": "Cable puller",
                "Present": True,
                "Hours": 10,
                "Status": "work",
                "Sheet": "September",
                "Project": "600",
            },
            {
                "Date": "2026-10-05",
                "Name": "Oct Person",
                "Position": "Cable puller",
                "Present": True,
                "Hours": 10,
                "Status": "work",
                "Sheet": "October",
                "Project": "600",
            },
            {
                "Date": "2026-10-06",
                "Name": "Oct Person",
                "Position": "Cable puller",
                "Present": True,
                "Hours": 10,
                "Status": "work",
                "Sheet": "October",
                "Project": "600",
            },
        ]
    )
    assert staffing_db.names_on_sheet(incoming, "October") == ["Oct Person"]
    counts = staffing_db.apply_ship_600_project_defaults(
        db,
        incoming=incoming,
        roster_names=["Sept Only", "Oct Person", "Main Worker"],
        user_email="planner@test.local",
    )
    assert counts["project_600"] == 1
    assert counts["project_598"] == 2
    people = [
        {"name": "Oct Person", "id": "Oct Person", "position": ""},
        {"name": "Sept Only", "id": "Sept Only", "position": ""},
        {"name": "Main Worker", "id": "Main Worker", "position": ""},
    ]
    by_name = {p["name"]: p for p in staffing_db.apply_roster_meta(db, people)}
    assert by_name["Oct Person"]["project"] == "600"
    assert by_name["Sept Only"]["project"] == "598"
    assert by_name["Main Worker"]["project"] == "598"


def test_parse_workforce_excel_tags_project(tmp_path):
    # Minimal sheet resembling Arbeitsstunden header
    import openpyxl

    path = tmp_path / "w600.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "October"
    ws.append(
        [
            "Name",
            "Last name",
            "First name",
            "Position",
            date(2026, 10, 1),
            date(2026, 10, 2),
        ]
    )
    ws.append(["Test Person", "Person", "Test", "Cable puller", 10, "holiday"])
    wb.save(path)

    df = parse_workforce_excel(path, year=2026, project="600")
    assert not df.empty
    assert set(df["Project"]) == {"600"}
    assert "Test Person" in set(df["Name"])
    assert person_key("Test Person")


def test_apply_default_project_rejects_unknown(db):
    with pytest.raises(staffing_db.StaffingError):
        staffing_db.apply_default_project(db, ["A"], project="999", user_email="x")


def test_dedupe_prefers_october_leave_over_september_empty():
    """September sheets often carry blank October day columns that must not wipe leave."""
    from datetime import date as date_cls

    df = pd.DataFrame(
        [
            {
                "Date": "2026-10-27",
                "Name": "Gáspár Péter",
                "Position": "Team lead",
                "Present": False,
                "Hours": None,
                "Status": "leave",
                "Sheet": "October",
                "Project": None,
            },
            {
                "Date": "2026-10-27",
                "Name": "Gáspár Péter",
                "Position": "Team lead",
                "Present": False,
                "Hours": None,
                "Status": "empty",
                "Sheet": "September",
                "Project": None,
            },
            {
                "Date": "2026-10-28",
                "Name": "Gáspár Péter",
                "Position": "Team lead",
                "Present": False,
                "Hours": None,
                "Status": "empty",
                "Sheet": "September",
                "Project": None,
            },
            {
                "Date": "2026-10-28",
                "Name": "Gáspár Péter",
                "Position": "Team lead",
                "Present": False,
                "Hours": None,
                "Status": "leave",
                "Sheet": "October",
                "Project": None,
            },
        ]
    )
    # Put empty rows last (the bug order from sort_values ties).
    df = pd.concat([df.iloc[[0, 2]], df.iloc[[1, 3]]], ignore_index=True)
    merged = board_svc.merge_workforce_upload(None, df, project=None)
    g = merged[merged["Name"] == "Gáspár Péter"].sort_values("Date")
    assert list(g["Status"]) == ["leave", "leave"]
    people = board_svc.list_people(merged, as_of=date_cls(2026, 10, 24))
    person = next(p for p in people if p["name"] == "Gáspár Péter")
    assert person["leave_ranges"]
    assert person["leave_ranges"][0]["start"] <= "2026-10-28"
