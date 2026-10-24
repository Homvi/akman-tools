"""Job categories for task staffing (independent of the Excel position wording)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable, Mapping

CATEGORIES: tuple[str, ...] = (
    "cable_puller",
    "electrician",
    "long_distance_lead",
    "local_cabling_lead",
    "electrician_lead",
)
LEAD_CATEGORIES: frozenset[str] = frozenset({"long_distance_lead", "local_cabling_lead", "electrician_lead"})

LABELS: dict[str, dict[str, str]] = {
    "hu": {
        "cable_puller": "Kábelhúzó",
        "electrician": "Villanyszerelő",
        "long_distance_lead": "Távolsági kábelhúzó csoportvezető",
        "local_cabling_lead": "Helyi kábelező csoportvezető",
        "electrician_lead": "Villanyszerelő csoportvezető",
    },
    "en": {
        "cable_puller": "Cable puller",
        "electrician": "Electrician",
        "long_distance_lead": "Long-distance cable pull lead",
        "local_cabling_lead": "Local cabling lead",
        "electrician_lead": "Electrician lead",
    },
    "de": {
        "cable_puller": "Kabelzieher",
        "electrician": "Elektriker",
        "long_distance_lead": "Vorarbeiter Fernkabelzug",
        "local_cabling_lead": "Vorarbeiter lokale Verkabelung",
        "electrician_lead": "Vorarbeiter Elektriker",
    },
}

# Excel position (casefolded) → category. Unlisted positions need a manual category.
_POSITION_GUESS: dict[str, str] = {
    "cable puller": "cable_puller",
    "kábelhúzó": "cable_puller",
    "electrician": "electrician",
    "electric": "electrician",
    "villanyszerelő": "electrician",
    "cable pull team leader": "long_distance_lead",
}


def category_label(category: str | None, lang: str = "hu") -> str:
    if not category:
        return ""
    return LABELS.get(lang, LABELS["en"]).get(category, category)


def is_category(value: Any) -> bool:
    return isinstance(value, str) and value in CATEGORIES


def guess_category(position: str | None) -> str | None:
    key = " ".join(str(position or "").split()).casefold()
    return _POSITION_GUESS.get(key)


def apply_categories(
    people: Iterable[dict[str, Any]],
    overrides: Mapping[str, str],
    *,
    key_of=lambda name: " ".join(str(name or "").split()).casefold(),
) -> list[dict[str, Any]]:
    """Set category/category_source on each person; manual overrides win over the guess."""
    out: list[dict[str, Any]] = []
    for person in people:
        p = dict(person)
        manual = overrides.get(key_of(p.get("name", "")))
        if is_category(manual):
            p["category"], p["category_source"] = manual, "manual"
        else:
            guess = guess_category(p.get("position"))
            p["category"], p["category_source"] = (guess, "auto") if guess else (None, None)
        if p["category"]:
            p["is_lead"] = p["category"] in LEAD_CATEGORIES
        out.append(p)
    return out


def normalize_requirements(raw: Any) -> dict[str, int]:
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, int] = {}
    for cat in CATEGORIES:
        try:
            n = int(raw.get(cat) or 0)
        except (TypeError, ValueError):
            n = 0
        n = max(0, min(n, 99))
        if n:
            out[cat] = n
    return out


def _next_week(today: date) -> tuple[date, date]:
    start = today - timedelta(days=today.weekday()) + timedelta(days=7)
    return start, start + timedelta(days=6)


def _leave_overlaps(person: Mapping[str, Any], start: date, end: date) -> bool:
    for r in person.get("leave_ranges") or []:
        try:
            a = date.fromisoformat(str(r.get("start"))[:10])
            b = date.fromisoformat(str(r.get("end") or r.get("start"))[:10])
        except ValueError:
            continue
        if a <= end and b >= start:
            return True
    return False


def requirements_summary(
    tasks: Iterable[Mapping[str, Any]],
    people: Iterable[Mapping[str, Any]],
    *,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Per category: needed (open tasks), assigned, roster, on leave now / next week, short."""
    day = today or date.today()
    nw_start, nw_end = _next_week(day)
    people = list(people)
    by_id = {str(p.get("id") or p.get("name")): p for p in people}
    open_tasks = [t for t in tasks if not t.get("done")]

    rows: list[dict[str, Any]] = []
    for cat in CATEGORIES:
        roster = [p for p in people if p.get("category") == cat]
        needed = sum(int((t.get("requirements") or {}).get(cat) or 0) for t in open_tasks)
        assigned = 0
        for t in open_tasks:
            for pid in [t.get("lead_id"), *(t.get("worker_ids") or [])]:
                if pid and by_id.get(str(pid), {}).get("category") == cat:
                    assigned += 1
        rows.append(
            {
                "category": cat,
                "needed": needed,
                "assigned": assigned,
                "roster": len(roster),
                "on_leave_now": sum(1 for p in roster if p.get("on_leave")),
                "leave_next_week": sum(1 for p in roster if _leave_overlaps(p, nw_start, nw_end)),
                "short": needed > len(roster),
            }
        )
    return rows
