from __future__ import annotations

import pandas as pd

from apps.api.services import workforce_board as board_svc


def test_is_team_lead_detection():
    assert board_svc.is_team_lead("Team lead")
    assert board_svc.is_team_lead("Csoportvezető")
    assert board_svc.is_team_lead("Vorarbeiter")
    assert not board_svc.is_team_lead("Cable puller")
    assert not board_svc.is_team_lead("Electrician")


def test_list_people_latest_position_and_lead_flag():
    from datetime import date

    df = pd.DataFrame(
        [
            {"Date": "2026-10-01", "Name": "Anna", "Position": "Cable puller", "Present": True, "Status": "work"},
            {"Date": "2026-10-02", "Name": "Anna", "Position": "Team lead", "Present": True, "Status": "work"},
            {"Date": "2026-10-02", "Name": "Béla", "Position": "Electrician", "Present": True, "Status": "work"},
            {"Date": "2026-10-02", "Name": "Cecil", "Position": "Office", "Present": False, "Status": "leave"},
            {"Date": "2026-10-01", "Name": "Dani", "Position": "Cable puller", "Present": True, "Status": "work"},
            {"Date": "2026-10-02", "Name": "Dani", "Position": "Cable puller", "Present": False, "Status": "leave"},
            {"Date": "2026-10-03", "Name": "Dani", "Position": "Cable puller", "Present": False, "Status": "leave"},
        ]
    )
    people = board_svc.list_people(df, as_of=date(2026, 10, 2))
    by_name = {p["name"]: p for p in people}
    assert by_name["Anna"]["position"] == "Team lead"
    assert by_name["Anna"]["is_lead"] is True
    assert by_name["Anna"]["available"] is True
    assert by_name["Anna"]["on_leave"] is False
    assert by_name["Béla"]["is_lead"] is False
    # Leave-only (no prior Present) still appears on the organisation roster.
    assert by_name["Cecil"]["on_leave"] is True
    assert by_name["Cecil"]["available"] is False
    assert by_name["Cecil"]["last_present"] is None
    assert by_name["Dani"]["on_leave"] is True
    assert by_name["Dani"]["leave_start"] == "2026-10-02"
    assert by_name["Dani"]["leave_end"] == "2026-10-03"
    assert by_name["Dani"]["as_of"] == "2026-10-02"


def test_list_people_hides_inactive_over_three_weeks():
    from datetime import date

    df = pd.DataFrame(
        [
            {"Date": "2026-09-01", "Name": "Old", "Position": "Cable puller", "Present": True, "Status": "work"},
            {"Date": "2026-10-20", "Name": "Fresh", "Position": "Cable puller", "Present": True, "Status": "work"},
            {"Date": "2026-10-01", "Name": "Border", "Position": "Electrician", "Present": True, "Status": "work"},
        ]
    )
    people = board_svc.list_people(df, as_of=date(2026, 10, 23), inactive_days=21)
    names = {p["name"] for p in people}
    assert names == {"Fresh"}


def test_list_people_keeps_new_names_without_present_mark():
    """Roster rows in the active window must show up even with no work cell yet."""
    from datetime import date

    df = pd.DataFrame(
        [
            {"Date": "2026-10-20", "Name": "OldHand", "Position": "Cable puller", "Present": True, "Status": "work"},
            {"Date": "2026-10-22", "Name": "NewHire", "Position": "Electrician", "Present": False, "Status": ""},
            {"Date": "2026-10-23", "Name": "OnLeave", "Position": "Cable puller", "Present": False, "Status": "leave"},
            {"Date": "2026-09-01", "Name": "Gone", "Position": "Helper", "Present": False, "Status": ""},
        ]
    )
    people = board_svc.list_people(df, as_of=date(2026, 10, 23), inactive_days=21)
    by_name = {p["name"]: p for p in people}
    assert set(by_name) == {"OldHand", "NewHire", "OnLeave"}
    assert by_name["NewHire"]["last_present"] is None
    assert by_name["NewHire"]["available"] is False
    assert by_name["OnLeave"]["on_leave"] is True


def test_list_people_merges_position_case_variants():
    from datetime import date

    df = pd.DataFrame(
        [
            {"Date": "2026-10-02", "Name": "A", "Position": "Iron worker", "Present": True},
            {"Date": "2026-10-02", "Name": "B", "Position": "Iron Worker", "Present": True},
            {"Date": "2026-10-02", "Name": "C", "Position": "Iron worker", "Present": True},
            {"Date": "2026-10-02", "Name": "D", "Position": "Site manager", "Present": True},
            {"Date": "2026-10-02", "Name": "E", "Position": "Site Manager", "Present": True},
        ]
    )
    people = board_svc.list_people(df, as_of=date(2026, 10, 2))
    positions = board_svc.unique_positions_from_people(people)
    assert len([p for p in positions if p.casefold() == "iron worker"]) == 1
    assert len([p for p in positions if p.casefold() == "site manager"]) == 1
    assert {p["position"] for p in people if p["name"] in {"A", "B", "C"}} == {"Iron worker"}
    assert len({p["position"] for p in people if p["name"] in {"D", "E"}}) == 1


def test_normalize_task_board_lead_and_workers(tmp_path, monkeypatch):
    monkeypatch.setattr(board_svc, "board_path", lambda: tmp_path / "workforce_board.json")
    saved = board_svc.save_board(
        {
            "tasks": [
                {
                    "id": "x1",
                    "title": "HV feeders",
                    "size": 4,
                    "lead_id": "Anna",
                    "worker_ids": ["Béla", "Anna", "Ghost", "Béla"],
                    "blocker": True,
                    "done": False,
                    "order": 0,
                },
                {
                    "title": "Pull 4012",
                    "lead_id": "Anna",  # already claimed by first task → dropped
                    "worker_ids": ["Cecil"],
                },
            ],
        }
    )
    assert "teams" not in saved
    assert "assignments" not in saved
    assert len(saved["tasks"]) == 2
    assert saved["tasks"][0]["lead_id"] == "Anna"
    assert saved["tasks"][0]["worker_ids"] == ["Béla", "Ghost"]
    assert saved["tasks"][0]["size"] == 4
    assert saved["tasks"][0]["blocker"] is True
    assert saved["tasks"][1]["lead_id"] is None
    assert saved["tasks"][1]["worker_ids"] == ["Cecil"]
    assert saved["updated_at"]

    loaded = board_svc.load_board()
    assert loaded["tasks"][0]["title"] == "HV feeders"


def test_migrate_legacy_teams_to_tasks(tmp_path, monkeypatch):
    monkeypatch.setattr(board_svc, "board_path", lambda: tmp_path / "workforce_board.json")
    saved = board_svc.save_board(
        {
            "teams": [{"id": "t1", "name": "Deck 3", "order": 0, "size": 5}],
            "assignments": {"Anna": "t1", "Béla": "t1"},
            "tasks": [
                {
                    "id": "old",
                    "team_id": "t1",
                    "title": "nested",
                    "assignee_ids": ["Cecil"],
                }
            ],
        }
    )
    assert len(saved["tasks"]) == 1
    assert saved["tasks"][0]["title"] == "Deck 3"
    assert saved["tasks"][0]["size"] == 5
    assert set(saved["tasks"][0]["worker_ids"]) == {"Anna", "Béla", "Cecil"}
    assert saved["tasks"][0]["start_date"] is None
    assert saved["tasks"][0]["blocker_note"] == ""


def test_normalize_task_dates_and_blocker_note(tmp_path, monkeypatch):
    monkeypatch.setattr(board_svc, "board_path", lambda: tmp_path / "workforce_board.json")
    saved = board_svc.save_board(
        {
            "tasks": [
                {
                    "title": "Swapped",
                    "start_date": "2026-11-14",
                    "end_date": "2026-10-27T00:00:00",
                    "blocker": True,
                    "blocker_note": "  waiting for tray  " + "x" * 600,
                },
                {"title": "Bad", "start_date": "nope", "end_date": ""},
            ]
        }
    )
    first, second = saved["tasks"]
    assert first["start_date"] == "2026-10-27"
    assert first["end_date"] == "2026-11-14"
    assert first["blocker_note"].startswith("waiting for tray")
    assert len(first["blocker_note"]) == 500
    assert second["start_date"] is None
    assert second["end_date"] is None


def test_requirements_normalized_and_drive_size(tmp_path, monkeypatch):
    monkeypatch.setattr(board_svc, "board_path", lambda: tmp_path / "workforce_board.json")
    saved = board_svc.save_board(
        {
            "tasks": [
                {"title": "Req", "size": 9, "requirements": {"cable_puller": 2, "long_distance_lead": "1", "x": 4}},
                {"title": "Legacy", "size": 3},
            ]
        }
    )
    req, legacy = saved["tasks"]
    assert req["requirements"] == {"cable_puller": 2, "long_distance_lead": 1}
    assert req["size"] == 3
    assert legacy["requirements"] == {}
    assert legacy["size"] == 3


def test_leave_missing_means_no_current_or_future_leave():
    from datetime import date

    rows = [
        {"Date": "2026-10-20", "Name": n, "Position": "Cable puller", "Present": True, "Status": "work"}
        for n in ("Past", "Future", "Now")
    ]
    rows += [
        {"Date": "2026-10-05", "Name": "Past", "Position": "Cable puller", "Present": False, "Status": "leave"},
        {"Date": "2026-11-10", "Name": "Future", "Position": "Cable puller", "Present": False, "Status": "leave"},
        {"Date": "2026-10-23", "Name": "Now", "Position": "Cable puller", "Present": False, "Status": "leave"},
        {"Date": "2026-10-26", "Name": "Now", "Position": "Cable puller", "Present": False, "Status": "leave"},
    ]
    people = board_svc.list_people(pd.DataFrame(rows), as_of=date(2026, 10, 23))
    missing = {p["name"] for p in people if not p["leave_ranges"]}
    assert missing == {"Past"}


def test_list_people_leave_ranges_bridge_weekends():
    from datetime import date

    rows = [{"Date": "2026-10-20", "Name": "Eva", "Position": "Cable puller", "Present": True, "Status": "work"}]
    # Fri 2026-10-30 + Mon/Tue 11-02..03 → one block; 11-16 → separate block
    for d in ("2026-10-30", "2026-11-02", "2026-11-03", "2026-11-16"):
        rows.append({"Date": d, "Name": "Eva", "Position": "Cable puller", "Present": False, "Status": "leave"})
    # A past block that ended before as_of is dropped
    rows.append({"Date": "2026-10-05", "Name": "Eva", "Position": "Cable puller", "Present": False, "Status": "leave"})
    people = board_svc.list_people(pd.DataFrame(rows), as_of=date(2026, 10, 23))
    eva = next(p for p in people if p["name"] == "Eva")
    assert eva["leave_ranges"] == [
        {"start": "2026-10-30", "end": "2026-11-03"},
        {"start": "2026-11-16", "end": "2026-11-16"},
    ]
