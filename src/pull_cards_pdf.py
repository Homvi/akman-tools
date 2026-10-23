from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.length_calc import format_meters, format_stichmass_label, nearest_end_stichmass
from src.stutzen_filter import cable_length, cable_route, enrich_stutzen_frame

LABELS: dict[str, dict[str, str]] = {
    "en": {
        "title": "Cable pulling list",
        "printed": "Printed",
        "cable": "Cable no.",
        "list": "List",
        "category": "Category",
        "length": "Length [m]",
        "status": "Status",
        "stichmass": "Stichmaß",
        "end_length": "Requested length",
        "start_device": "Start device (A)",
        "end_device": "End device (E)",
        "location": "Location",
        "node": "Node",
        "route": "Route",
        "remark": "Remark",
        "filter": "Filter criteria",
        "page": "Page {page}",
        "empty": "(none)",
    },
    "hu": {
        "title": "Kábel húzólista",
        "printed": "Nyomtatva",
        "cable": "Kabelnr.",
        "list": "Liste",
        "category": "Kategória",
        "length": "Hossz [m]",
        "status": "Státusz",
        "stichmass": "Stichmaß",
        "end_length": "Kért méret",
        "start_device": "Kezdő készülék (A)",
        "end_device": "Cél készülék (E)",
        "location": "Hely",
        "node": "Csomópont",
        "route": "Nyomvonal",
        "remark": "Megjegyzés",
        "filter": "Szűrési kritérium",
        "page": "{page}. oldal",
        "empty": "(nincs)",
    },
    "de": {
        "title": "Kabelziehliste",
        "printed": "Gedruckt",
        "cable": "Kabelnr.",
        "list": "Liste",
        "category": "Kategorie",
        "length": "Länge [m]",
        "status": "Status",
        "stichmass": "Stichmaß",
        "end_length": "Anschlusslänge",
        "start_device": "Startgerät (A)",
        "end_device": "Zielgerät (E)",
        "location": "Ort",
        "node": "Knoten",
        "route": "Pfad",
        "remark": "Bemerkung",
        "filter": "Filterkriterien",
        "page": "Blatt {page}",
        "empty": "(keine)",
    },
}


def _labels(lang: str) -> dict[str, str]:
    key = (lang or "en").strip().lower()
    return LABELS.get(key, LABELS["en"])


def _txt(value: Any, empty: str = "") -> str:
    if value is None or value is pd.NA:
        return empty
    try:
        if pd.isna(value):
            return empty
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() in {"nan", "<na>", "none", "nat"}:
        return empty
    return text


def _fmt_m(value: Any) -> str:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return _txt(value)


def _num(value: Any) -> float:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        text = _txt(value).replace(",", ".")
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0


def _end_stichmass_label(row: pd.Series, route: str, *, end: str) -> str:
    stuetze, result = nearest_end_stichmass(
        route,
        end=end,
        node_a=_txt(row.get("Knoten_A")),
        node_e=_txt(row.get("Knoten_E")),
        aln_a=_num(row.get("Aln_A")),
        aln_e=_num(row.get("Aln_E")),
    )
    return format_stichmass_label(stuetze, result)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _highlight_nodes(route: str, nodes: list[str] | None) -> str:
    """Wrap matching filter nodes in <b> for Paragraph markup."""
    escaped = _escape(route)
    if not nodes:
        return escaped
    import re

    sorted_nodes = sorted((n for n in nodes if n), key=len, reverse=True)
    for node in sorted_nodes:
        pattern = rf"(?<![a-zA-Z0-9.])({re.escape(_escape(node))})(?![a-zA-Z0-9.])"
        escaped = re.sub(pattern, r"<b>\1</b>", escaped)
    return escaped


class _HR(Flowable):
    def __init__(self, width: float, thickness: float = 0.6, color=colors.black):
        super().__init__()
        self._width = width
        self._thickness = thickness
        self._color = color
        self.height = thickness + 2

    def wrap(self, availWidth, availHeight):
        return self._width, self.height

    def draw(self):
        self.canv.setStrokeColor(self._color)
        self.canv.setLineWidth(self._thickness)
        self.canv.line(0, 1, self._width, 1)


def _cell(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_escape(text) if text else "—", style)


def _build_card(
    row: pd.Series,
    *,
    labels: dict[str, str],
    styles: dict[str, ParagraphStyle],
    content_width: float,
    highlight_nodes: list[str] | None,
) -> KeepTogether:
    kabelnr = _txt(row.get("Kabelnr") or row.get("Kabel_raw"), labels["empty"])
    liste = _txt(row.get("Liste") or row.get("Kabelbez"))
    category = _txt(row.get("Category") or row.get("Artikel") or row.get("Typ") or row.get("Kabeltyp"))
    length = _fmt_m(cable_length(row) if "Length_m" in row.index or "Laenge" in row.index else row.get("Length_m"))
    status = _txt(row.get("Pull_status"), labels["empty"])
    # Kért méret at each end = Aln_A / Aln_E (Anschlusslänge), not Stichmaß.
    end_len_a = (
        format_meters(_num(row.get("Aln_A")))
        if "Aln_A" in row.index and _txt(row.get("Aln_A")) != ""
        else labels["empty"]
    )
    end_len_e = (
        format_meters(_num(row.get("Aln_E")))
        if "Aln_E" in row.index and _txt(row.get("Aln_E")) != ""
        else labels["empty"]
    )

    geraet_a = _txt(row.get("Geraet_A") or row.get("A_Geraet"), labels["empty"])
    geraet_e = _txt(row.get("Geraet_E") or row.get("E_Geraet"), labels["empty"])
    ort_a = _txt(row.get("Ort_A"), labels["empty"])
    ort_e = _txt(row.get("Ort_E"), labels["empty"])
    knoten_a = _txt(row.get("Knoten_A"), labels["empty"])
    knoten_e = _txt(row.get("Knoten_E"), labels["empty"])
    route = cable_route(row)
    stich_a = _end_stichmass_label(row, route, end="A") or labels["empty"]
    stich_e = _end_stichmass_label(row, route, end="E") or labels["empty"]
    route_html = _highlight_nodes(route, highlight_nodes) if route else _escape(labels["empty"])
    remark = _txt(
        row.get("Notizen") or row.get("Bemerkung") or row.get("Note"),
        labels["empty"],
    )

    header = Table(
        [
            [
                Paragraph(f"<b>{_escape(labels['cable'])}</b><br/>{_escape(kabelnr)}", styles["value"]),
                Paragraph(f"<b>{_escape(labels['list'])}</b><br/>{_escape(liste or '—')}", styles["value"]),
                Paragraph(f"<b>{_escape(labels['category'])}</b><br/>{_escape(category or '—')}", styles["value"]),
                Paragraph(f"<b>{_escape(labels['length'])}</b><br/>{_escape(length or '—')}", styles["value"]),
            ]
        ],
        colWidths=[content_width * 0.28, content_width * 0.22, content_width * 0.32, content_width * 0.18],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ]
        )
    )

    progress = Table(
        [
            [
                Paragraph(
                    f"<b>{_escape(labels['status'])}</b><br/>{_escape(status)}",
                    styles["value"],
                ),
                Paragraph(
                    f"<b>{_escape(labels['stichmass'])}</b><br/>"
                    f"A: {_escape(stich_a)}<br/>E: {_escape(stich_e)}",
                    styles["value"],
                ),
            ]
        ],
        colWidths=[content_width * 0.35, content_width * 0.65],
    )
    progress.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ]
        )
    )

    ends = Table(
        [
            [
                Paragraph(
                    f"<b>{_escape(labels['start_device'])}</b><br/>{_escape(geraet_a)}"
                    f"<br/><font size='7'>{_escape(labels['location'])}: {_escape(ort_a)}"
                    f" · {_escape(labels['node'])}: {_escape(knoten_a)}</font>"
                    f"<br/><b>{_escape(labels['end_length'])}</b>: {_escape(end_len_a)}",
                    styles["value"],
                ),
                Paragraph(
                    f"<b>{_escape(labels['end_device'])}</b><br/>{_escape(geraet_e)}"
                    f"<br/><font size='7'>{_escape(labels['location'])}: {_escape(ort_e)}"
                    f" · {_escape(labels['node'])}: {_escape(knoten_e)}</font>"
                    f"<br/><b>{_escape(labels['end_length'])}</b>: {_escape(end_len_e)}",
                    styles["value"],
                ),
            ]
        ],
        colWidths=[content_width * 0.5, content_width * 0.5],
    )
    ends.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ]
        )
    )

    route_block = Table(
        [
            [
                Paragraph(f"<b>{_escape(labels['route'])}</b>", styles["label"]),
            ],
            [Paragraph(route_html, styles["route"])],
        ],
        colWidths=[content_width],
    )
    route_block.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.black),
            ]
        )
    )

    remark_block = Table(
        [
            [
                Paragraph(
                    f"<b>{_escape(labels['remark'])}</b><br/>{_escape(remark)}",
                    styles["value"],
                ),
            ],
        ],
        colWidths=[content_width],
    )
    remark_block.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.black),
            ]
        )
    )

    return KeepTogether(
        [
            header,
            progress,
            ends,
            route_block,
            remark_block,
            Spacer(1, 3 * mm),
        ]
    )


def build_pull_cards_pdf(
    df: pd.DataFrame,
    *,
    filter_note: str = "",
    printed_at: datetime | None = None,
    lang: str = "en",
    highlight_nodes: list[str] | None = None,
    title: str | None = None,
) -> bytes:
    """Build A4 portrait pulling-card PDF for the given cable rows."""
    labels = _labels(lang)
    printed = printed_at or datetime.now()
    stamp = printed.strftime("%d.%m.%Y %H:%M")
    frame = enrich_stutzen_frame(df) if df is not None else pd.DataFrame()

    page = landscape(A4)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm,
        title=title or labels["title"],
    )
    content_width = page[0] - doc.leftMargin - doc.rightMargin

    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "PullTitle",
            parent=base["Heading1"],
            fontSize=14,
            leading=18,
            spaceAfter=2,
            alignment=TA_LEFT,
        ),
        "meta": ParagraphStyle(
            "PullMeta",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#333333"),
        ),
        "label": ParagraphStyle(
            "PullLabel",
            parent=base["Normal"],
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#444444"),
        ),
        "value": ParagraphStyle(
            "PullValue",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
        ),
        "route": ParagraphStyle(
            "PullRoute",
            parent=base["Normal"],
            fontName="Courier",
            fontSize=7.5,
            leading=9.5,
            alignment=TA_LEFT,
        ),
        "footer": ParagraphStyle(
            "PullFooter",
            parent=base["Normal"],
            fontSize=7.5,
            leading=9,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#222222"),
        ),
    }

    story: list[Any] = []
    head = Table(
        [
            [
                Paragraph(f"<b>{_escape(title or labels['title'])}</b>", styles["title"]),
                Paragraph(f"{_escape(labels['printed'])}: {_escape(stamp)}", styles["meta"]),
            ]
        ],
        colWidths=[content_width * 0.62, content_width * 0.38],
    )
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    story.append(head)
    story.append(_HR(content_width, 1.0))
    story.append(Spacer(1, 3 * mm))

    if frame.empty:
        story.append(Paragraph(_escape(labels["empty"]), styles["value"]))
    else:
        for _, row in frame.iterrows():
            story.append(
                _build_card(
                    row,
                    labels=labels,
                    styles=styles,
                    content_width=content_width,
                    highlight_nodes=highlight_nodes,
                )
            )

    note = _txt(filter_note)
    footer_note = note

    def _on_page(canvas, doc_):
        canvas.saveState()
        page_label = labels["page"].format(page=doc_.page)
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(page[0] - 12 * mm, 8 * mm, page_label)
        if footer_note:
            canvas.setFont("Helvetica", 7)
            prefix = f"{labels['filter']}: "
            max_w = page[0] - 24 * mm - 40
            text = prefix + footer_note
            # truncate for single footer line
            while canvas.stringWidth(text, "Helvetica", 7) > max_w and len(text) > 20:
                text = text[:-4] + "…"
            canvas.drawString(12 * mm, 8 * mm, text)
        canvas.restoreState()

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buffer.getvalue()
