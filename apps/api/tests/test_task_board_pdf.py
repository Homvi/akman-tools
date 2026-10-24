from __future__ import annotations

from datetime import date

from src.staffing_categories import apply_categories
from src.task_board_pdf import build_task_board_pdf


def test_task_board_pdf_renders_all_sections():
    people = apply_categories(
        [
            {"id": "Kovács Ödön", "name": "Kovács Ödön", "position": "Cable pull team leader"},
            {"id": "Szűts Győző", "name": "Szűts Győző", "position": "Cable puller",
             "leave_ranges": [{"start": "2026-11-03", "end": "2026-11-05"}]},
        ],
        {},
    )
    board = {
        "updated_at": "2026-10-24T08:00:00+00:00",
        "tasks": [
            {"id": "t1", "title": "Deck 3 – hosszú húzás", "size": 3, "order": 0,
             "requirements": {"long_distance_lead": 1, "cable_puller": 2},
             "lead_id": "Kovács Ödön", "worker_ids": ["Szűts Győző"],
             "start_date": "2026-11-02", "end_date": "2026-11-06",
             "blocker": True, "blocker_note": "Tálca hiányzik", "done": False},
            {"id": "t2", "title": "Kész feladat", "size": 0, "order": 1, "requirements": {},
             "lead_id": None, "worker_ids": [], "start_date": None, "end_date": None,
             "blocker": False, "blocker_note": "", "done": True},
        ],
    }
    notes = {"t1": [{"text": "Anyag csütörtökön jön", "author_email": "p@x", "created_at": "2026-10-23T10:00:00"}]}
    for lang in ("hu", "en", "de"):
        pdf = build_task_board_pdf(board, people, notes, lang=lang, today=date(2026, 10, 24))
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 2000


def test_task_board_pdf_empty_board():
    pdf = build_task_board_pdf({"tasks": []}, [], lang="xx")
    assert pdf.startswith(b"%PDF")
