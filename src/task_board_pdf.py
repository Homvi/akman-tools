"""Printable overview of the Csapatok board: staffing summary + one block per task."""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable, Mapping
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.staffing_categories import category_label, requirements_summary

# Helvetica has no ő/ű, so prefer a TTF with full Latin Extended-A coverage.
_FONT_CANDIDATES: tuple[tuple[str, str], ...] = (
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
)

LABELS: dict[str, dict[str, str]] = {
    "hu": {
        "title": "Csapatok – feladatok",
        "printed": "Nyomtatva",
        "updated": "Tábla frissítve",
        "summary": "Létszámigény kategóriánként",
        "category": "Kategória",
        "needed": "Szükséges",
        "roster": "Létszám",
        "assigned": "Beosztva",
        "leave_now": "Most szabin",
        "leave_next": "Jövő héten szabin",
        "totals": "{tasks} feladat · {open} nyitott · {blocked} blokkolt · {done} kész",
        "period": "Időszak",
        "status": "Státusz",
        "requirements": "Elvárás",
        "headcount": "Létszám",
        "lead": "Csoportvezető",
        "members": "Csapat",
        "name": "Név",
        "position": "Pozíció",
        "leave": "Szabadság",
        "blocker": "Blokkoló ok",
        "notes": "Megjegyzések",
        "no_dates": "nincs dátum",
        "no_lead": "nincs kijelölve",
        "no_members": "Még nincs beosztott ember.",
        "none": "—",
        "active": "Folyamatban",
        "blocked": "Blokkolva",
        "done": "Kész",
        "conflict": "ÜTKÖZÉS",
        "short": "kevés",
        "no_tasks": "Nincs feladat a táblán.",
        "unclassified": "Nincs besorolva",
    },
    "en": {
        "title": "Teams – tasks",
        "printed": "Printed",
        "updated": "Board updated",
        "summary": "Staffing demand by category",
        "category": "Category",
        "needed": "Needed",
        "roster": "Roster",
        "assigned": "Assigned",
        "leave_now": "On leave now",
        "leave_next": "Leave next week",
        "totals": "{tasks} tasks · {open} open · {blocked} blocked · {done} done",
        "period": "Period",
        "status": "Status",
        "requirements": "Requirements",
        "headcount": "Headcount",
        "lead": "Lead",
        "members": "Team",
        "name": "Name",
        "position": "Position",
        "leave": "Leave",
        "blocker": "Blocker",
        "notes": "Notes",
        "no_dates": "no dates",
        "no_lead": "not assigned",
        "no_members": "Nobody assigned yet.",
        "none": "—",
        "active": "In progress",
        "blocked": "Blocked",
        "done": "Done",
        "conflict": "CONFLICT",
        "short": "short",
        "no_tasks": "No tasks on the board.",
        "unclassified": "Unclassified",
    },
    "de": {
        "title": "Teams – Aufgaben",
        "printed": "Gedruckt",
        "updated": "Tafel aktualisiert",
        "summary": "Personalbedarf nach Kategorie",
        "category": "Kategorie",
        "needed": "Bedarf",
        "roster": "Bestand",
        "assigned": "Eingeteilt",
        "leave_now": "Jetzt Urlaub",
        "leave_next": "Urlaub nächste Woche",
        "totals": "{tasks} Aufgaben · {open} offen · {blocked} blockiert · {done} erledigt",
        "period": "Zeitraum",
        "status": "Status",
        "requirements": "Anforderung",
        "headcount": "Kopfzahl",
        "lead": "Vorarbeiter",
        "members": "Team",
        "name": "Name",
        "position": "Position",
        "leave": "Urlaub",
        "blocker": "Blocker",
        "notes": "Notizen",
        "no_dates": "kein Datum",
        "no_lead": "nicht zugewiesen",
        "no_members": "Noch niemand eingeteilt.",
        "none": "—",
        "active": "In Arbeit",
        "blocked": "Blockiert",
        "done": "Erledigt",
        "conflict": "KONFLIKT",
        "short": "zu wenig",
        "no_tasks": "Keine Aufgaben auf der Tafel.",
        "unclassified": "Nicht eingestuft",
    },
}

TEAL = colors.HexColor("#0F766E")
RED = colors.HexColor("#B91C1C")
RED_BG = colors.HexColor("#FEE2E2")
GREY = colors.HexColor("#6B7280")
LIGHT = colors.HexColor("#F3F4F6")
LINE = colors.HexColor("#D1D5DB")
STATUS_COLOR = {"active": TEAL, "blocked": RED, "done": GREY}


def _register_fonts() -> tuple[str, str]:
    if "TaskBoardSans" in pdfmetrics.getRegisteredFontNames():
        return "TaskBoardSans", "TaskBoardSans-Bold"
    for regular, bold in _FONT_CANDIDATES:
        if Path(regular).is_file() and Path(bold).is_file():
            pdfmetrics.registerFont(TTFont("TaskBoardSans", regular))
            pdfmetrics.registerFont(TTFont("TaskBoardSans-Bold", bold))
            return "TaskBoardSans", "TaskBoardSans-Bold"
    return "Helvetica", "Helvetica-Bold"


def _labels(lang: str) -> dict[str, str]:
    return LABELS.get(lang, LABELS["en"])


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _fmt_day(d: date | None) -> str:
    return d.strftime("%Y.%m.%d") if d else ""


def _fmt_range(start: Any, end: Any) -> str:
    a, b = _day(start), _day(end) or _day(start)
    if not a:
        return ""
    if not b or b == a:
        return _fmt_day(a)
    return f"{_fmt_day(a)} – {_fmt_day(b)}"


def _status(task: Mapping[str, Any]) -> str:
    if task.get("done"):
        return "done"
    if task.get("blocker"):
        return "blocked"
    return "active"


def _sort_key(task: Mapping[str, Any]):
    status = _status(task)
    start = _day(task.get("start_date"))
    return (status == "done", start is None, start or date.max, int(task.get("order") or 0))


def _overlap(person: Mapping[str, Any], start: date | None, end: date | None) -> dict[str, str] | None:
    if not start:
        return None
    end = end or start
    for r in person.get("leave_ranges") or []:
        a, b = _day(r.get("start")), _day(r.get("end")) or _day(r.get("start"))
        if a and b and a <= end and b >= start:
            return r
    return None


def _leave_text(person: Mapping[str, Any]) -> str:
    ranges = person.get("leave_ranges") or []
    return ", ".join(_fmt_range(r.get("start"), r.get("end")) for r in ranges[:3])


def build_task_board_pdf(
    board: Mapping[str, Any],
    people: Iterable[Mapping[str, Any]],
    notes: Mapping[str, list[Mapping[str, Any]]] | None = None,
    *,
    lang: str = "hu",
    today: date | None = None,
) -> bytes:
    font, bold = _register_fonts()
    lbl = _labels(lang)
    notes = notes or {}
    day = today or date.today()
    people = list(people)
    by_id = {str(p.get("id") or p.get("name")): p for p in people}
    tasks = sorted(board.get("tasks") or [], key=_sort_key)

    base = ParagraphStyle("base", fontName=font, fontSize=8.5, leading=11)
    small = ParagraphStyle("small", parent=base, fontSize=7.5, leading=9.5, textColor=GREY)
    h1 = ParagraphStyle("h1", parent=base, fontName=bold, fontSize=16, leading=20)
    h2 = ParagraphStyle("h2", parent=base, fontName=bold, fontSize=11, leading=14, spaceBefore=4, spaceAfter=4)
    cell_bold = ParagraphStyle("cellb", parent=base, fontName=bold)
    task_title = ParagraphStyle("tt", parent=base, fontName=bold, fontSize=11, leading=14, textColor=colors.white)

    def p(text: Any, style: ParagraphStyle = base) -> Paragraph:
        return Paragraph(escape(str(text if text is not None else "")).replace("\n", "<br/>"), style)

    def colored(text: str, color, style: ParagraphStyle = base, is_bold: bool = False) -> Paragraph:
        face = bold if is_bold else font
        return Paragraph(f'<font name="{face}" color="{color.hexval()}">{escape(text)}</font>', style)

    page_w = A4[0] - 24 * mm
    story: list[Any] = []

    printed = datetime.now().strftime("%Y.%m.%d %H:%M")
    meta = f"{lbl['printed']}: {printed}"
    if board.get("updated_at"):
        meta += f" · {lbl['updated']}: {str(board['updated_at'])[:16].replace('T', ' ')}"
    story += [p(lbl["title"], h1), p(meta, small), Spacer(1, 4 * mm)]

    counts = {s: sum(1 for t in tasks if _status(t) == s) for s in ("active", "blocked", "done")}
    story.append(
        p(
            lbl["totals"].format(
                tasks=len(tasks), open=counts["active"] + counts["blocked"], blocked=counts["blocked"], done=counts["done"]
            ),
            cell_bold,
        )
    )
    story.append(Spacer(1, 3 * mm))

    # --- Summary -------------------------------------------------------------
    story.append(p(lbl["summary"], h2))
    rows = requirements_summary(tasks, people, today=day)
    head = [lbl["category"], lbl["needed"], lbl["roster"], lbl["assigned"], lbl["leave_now"], lbl["leave_next"]]
    data: list[list[Any]] = [[p(h, cell_bold) for h in head]]
    style_cmds: list[tuple] = []
    for i, row in enumerate(rows, start=1):
        need = f"{row['needed']}/{row['roster']}" + (f"  ({lbl['short']})" if row["short"] else "")
        data.append(
            [
                p(category_label(row["category"], lang)),
                colored(need, RED, base, True) if row["short"] else p(need),
                p(row["roster"]),
                p(row["assigned"]),
                p(row["on_leave_now"] or ""),
                p(row["leave_next_week"] or ""),
            ]
        )
        if row["short"]:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), RED_BG))
    unclassified = sum(1 for person in people if not person.get("category"))
    if unclassified:
        data.append([p(lbl["unclassified"], small), p(""), p(unclassified, small), p(""), p(""), p("")])
    widths = [page_w * w for w in (0.36, 0.14, 0.11, 0.11, 0.13, 0.15)]
    summary = Table(data, colWidths=widths, repeatRows=1)
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                *style_cmds,
            ]
        )
    )
    story += [summary, Spacer(1, 6 * mm)]

    if not tasks:
        story.append(p(lbl["no_tasks"]))

    # --- Tasks (one task per page) -------------------------------------------
    for task in tasks:
        story.append(PageBreak())
        status = _status(task)
        start, end = _day(task.get("start_date")), _day(task.get("end_date"))
        worker_ids = [pid for pid in (task.get("worker_ids") or []) if pid]
        members = [by_id.get(str(pid)) or {"id": pid, "name": pid} for pid in worker_ids]
        if task.get("lead_id"):
            lead_person = by_id.get(str(task.get("lead_id"))) or {
                "id": task.get("lead_id"),
                "name": task.get("lead_id"),
            }
        else:
            lead_person = None
        # Team table: lead + workers. Headcount includes lead when lead_counts
        # (lead is then also in worker_ids — avoid double-count).
        lead_id = str(task.get("lead_id") or "")
        lead_in_workers = bool(lead_id) and any(str(m.get("id") or m.get("name")) == lead_id for m in members)
        listed = ([lead_person] if lead_person and not lead_in_workers else []) + members
        headcount = len(members)
        if task.get("lead_counts") and lead_person and not lead_in_workers:
            headcount += 1

        block: list[Any] = []
        title_bar = Table(
            [[p(task.get("title") or "", task_title), colored(lbl[status], colors.white, base, True)]],
            colWidths=[page_w * 0.78, page_w * 0.22],
        )
        title_bar.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), STATUS_COLOR[status]),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        block.append(title_bar)

        lead = lead_person
        info = [
            [p(lbl["period"], cell_bold), p(_fmt_range(start, end) or lbl["no_dates"])],
            [p(lbl["headcount"], cell_bold), p(str(headcount))],
            [p(lbl["lead"], cell_bold), p((lead or {}).get("name") or task.get("lead_id") or lbl["no_lead"])],
        ]
        info_table = Table(info, colWidths=[page_w * 0.2, page_w * 0.8])
        info_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                    ("LINEBELOW", (0, -1), (-1, -1), 0.4, LINE),
                ]
            )
        )
        block.append(info_table)

        if status == "blocked" or (task.get("blocker") and task.get("blocker_note")):
            box = Table(
                [[colored(f"{lbl['blocker']}: {task.get('blocker_note') or lbl['none']}", RED, base, True)]],
                colWidths=[page_w],
            )
            box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), RED_BG), ("BOX", (0, 0), (-1, -1), 0.6, RED)]))
            block += [Spacer(1, 1.5 * mm), box]

        block.append(Spacer(1, 1.5 * mm))
        if listed:
            mrows: list[list[Any]] = [[p(h, cell_bold) for h in (lbl["name"], lbl["category"], lbl["position"], lbl["leave"])]]
            mstyle: list[tuple] = []
            for i, m in enumerate(listed, start=1):
                is_lead = str(m.get("id") or m.get("name")) == str(task.get("lead_id"))
                conflict = _overlap(m, start, end) if status != "done" else None
                name = f"★ {m.get('name')}" if is_lead else str(m.get("name") or "")
                leave = _leave_text(m)
                mrows.append(
                    [
                        p(name, cell_bold if is_lead else base),
                        p(category_label(m.get("category"), lang) or lbl["none"]),
                        p(m.get("position") or ""),
                        colored(f"{lbl['conflict']}: {_fmt_range(conflict.get('start'), conflict.get('end'))}", RED, base, True)
                        if conflict
                        else p(leave, small),
                    ]
                )
                if conflict:
                    mstyle.append(("BACKGROUND", (0, i), (-1, i), RED_BG))
            mt = Table(mrows, colWidths=[page_w * w for w in (0.3, 0.28, 0.18, 0.24)], repeatRows=1)
            mt.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                        ("GRID", (0, 0), (-1, -1), 0.3, LINE),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        *mstyle,
                    ]
                )
            )
            block.append(mt)
        else:
            block.append(p(lbl["no_members"], small))

        task_notes = notes.get(str(task.get("id"))) or []
        if task_notes:
            block += [Spacer(1, 1.5 * mm), p(f"{lbl['notes']} ({len(task_notes)})", cell_bold)]
            for n in task_notes:
                when = str(n.get("created_at") or "")[:16].replace("T", " ")
                block.append(p(f"{when} · {n.get('author_email') or ''}", small))
                block.append(p(n.get("text") or "", base))

        if len(listed) <= 15 and len(task_notes) <= 5:
            story.append(KeepTogether(block))
        else:
            story.append(KeepTogether(block[:2]))
            story += block[2:]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(font, 7)
        canvas.setFillColor(GREY)
        canvas.drawRightString(A4[0] - 12 * mm, 8 * mm, f"{lbl['title']} · {doc.page}")
        canvas.restoreState()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm,
        title=lbl["title"],
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
