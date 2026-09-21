from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass

import pandas as pd

from src.dates import is_pulled

_DIST = re.compile(r"[\d]+([,.][\d]+)?")
_PAREN = re.compile(r"\([^)]+\)")
_TOKEN = re.compile(r"\S+(?:\s+\([^)]*\))?")
_EMPTY = {"", "<NA>", "nan", "None"}

STATUS_COMPLETE = "complete"
STATUS_PARTIAL = "partial"
STATUS_NONE = "none"

STATUS_LABELS = {
    STATUS_COMPLETE: "Teljesen leadva (van verlegt dátum) — a teljes nyomvonal behúzottnak számít.",
    STATUS_PARTIAL: "Megállítva — van részlegesen behúzott szakasz (Startsegment → Endsegment).",
    STATUS_NONE: "Nincs behúzás — nincs Startsegment / megállás ezen a kábelen.",
}

_COLORS = {
    "pulled": "#fb923c",
    "selected": "#38bdf8",
    "overlap": "#f43f5e",
    "plain": "#e2e8f0",
}


@dataclass
class CalcResult:
    ok: bool
    meters: float = 0.0
    error: str = ""


@dataclass
class OverlapAdvice:
    has_overlap: bool
    pulled_start: str
    pulled_end: str
    selected_start: str
    selected_end: str
    overlap_start: str
    overlap_end: str
    suggest_start: str
    suggest_end: str
    message: str


def parse_distance(text) -> float:
    match = _DIST.search(str(text or ""))
    if not match:
        return 0.0
    return float(match.group(0).replace(",", "."))


def parse_route(route_str: str) -> tuple[list[str], list[float]]:
    text = str(route_str or "").strip()
    nodes = [part.strip() for part in _PAREN.sub("|", text).split("|") if part.strip()]
    distances = [parse_distance(part) for part in _PAREN.findall(text)]
    return nodes, distances


def format_meters(value: float) -> str:
    return f"{value:.1f}".replace(".", ",") + " m"


def _cell_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text in _EMPTY or text.lower() in {"nan", "<na>", "none"} else text


def latest_pull_ends(row: pd.Series) -> tuple[str, str]:
    """First Startsegment and latest Endsegment among filled pull slots."""
    start = ""
    end = ""
    for slot in (1, 2, 3):
        slot_start = _cell_text(row.get(f"Startsegment_{slot}"))
        slot_end = _cell_text(row.get(f"Endsegment_{slot}"))
        if not slot_start and not slot_end:
            continue
        if not start and slot_start:
            start = slot_start
        if slot_end:
            end = slot_end
        elif slot_start:
            end = slot_start
    if not start:
        start = end
    return start, end


def has_verlegt_date(row: pd.Series) -> bool:
    """True only when verlegt is a real date — never from Pull_status text."""
    return is_pulled(row.get("verlegt"))


def cable_pull_status(row: pd.Series) -> str:
    """
    complete = has verlegt date
    partial  = has Start/End segment but no verlegt
    none     = no pull activity

    Important: Pull_status "Not pulled" must NOT count as complete
    (substring "pulled" is a trap).
    """
    if has_verlegt_date(row):
        return STATUS_COMPLETE
    start, end = latest_pull_ends(row)
    if start or end:
        return STATUS_PARTIAL
    return STATUS_NONE


def cable_status_message(row: pd.Series) -> str:
    status = cable_pull_status(row)
    base = STATUS_LABELS[status]
    if status == STATUS_PARTIAL:
        start, end = latest_pull_ends(row)
        return f"{base} Már behúzott szakasz: {start or '—'} → {end or '—'}."
    return base


def _ordered_span(nodes: list[str], a: str, b: str) -> tuple[int, int] | None:
    a = str(a or "").strip()
    b = str(b or "").strip()
    if not a or not b:
        return None
    try:
        i = nodes.index(a)
        j = nodes.index(b)
    except ValueError:
        return None
    return (i, j) if i <= j else (j, i)


def _token_roles(
    n: int,
    pulled: tuple[int, int] | None,
    selected: tuple[int, int] | None,
) -> list[str]:
    roles = ["plain"] * n
    if pulled:
        for i in range(pulled[0], pulled[1] + 1):
            roles[i] = "pulled"
    if selected:
        for i in range(selected[0], selected[1] + 1):
            if roles[i] == "pulled":
                roles[i] = "overlap"
            else:
                roles[i] = "selected"
    return roles


def highlight_route_layers(
    route: str,
    *,
    pulled_start: str = "",
    pulled_end: str = "",
    selected_start: str = "",
    selected_end: str = "",
) -> str:
    """HTML route with pulled / selected / overlap coloring."""
    text = str(route or "").strip()
    if not text:
        return ""
    nodes, _ = parse_route(text)
    tokens = _TOKEN.findall(text.replace("\n", " "))
    if not nodes:
        return html.escape(text)

    pulled = _ordered_span(nodes, pulled_start, pulled_end)
    selected = _ordered_span(nodes, selected_start, selected_end)
    roles = _token_roles(len(nodes), pulled, selected)

    if len(tokens) != len(nodes):
        escaped = html.escape(text)
        for idx, role in enumerate(roles):
            if role == "plain":
                continue
            color = _COLORS[role]
            node = nodes[idx]
            pattern = rf"(?<![a-zA-Z0-9.])({re.escape(html.escape(node))})(?![a-zA-Z0-9.])"
            escaped = re.sub(
                pattern,
                rf'<mark style="background:{color};color:#0f172a;font-weight:800;padding:2px 6px;border-radius:4px;">\1</mark>',
                escaped,
                count=1,
            )
        return escaped

    parts: list[str] = []
    for i, token in enumerate(tokens):
        role = roles[i] if i < len(roles) else "plain"
        escaped_token = html.escape(token)
        if role == "plain":
            parts.append(escaped_token)
        else:
            color = _COLORS[role]
            parts.append(
                f'<mark data-role="{role}" style="background:{color};color:#0f172a;font-weight:700;'
                f'padding:2px 4px;border-radius:4px;">{escaped_token}</mark>'
            )
    return " ".join(parts)


def highlight_pulled_segment(route: str, start: str, end: str) -> str:
    return highlight_route_layers(route, pulled_start=start, pulled_end=end)


def analyze_overlap(
    route: str,
    pulled_start: str,
    pulled_end: str,
    selected_start: str,
    selected_end: str,
) -> OverlapAdvice:
    nodes, _ = parse_route(route)
    pulled = _ordered_span(nodes, pulled_start, pulled_end)
    selected = _ordered_span(nodes, selected_start, selected_end)
    empty = OverlapAdvice(
        False,
        str(pulled_start or "").strip(),
        str(pulled_end or "").strip(),
        str(selected_start or "").strip(),
        str(selected_end or "").strip(),
        "",
        "",
        "",
        "",
        "",
    )
    if not nodes or pulled is None or selected is None:
        return empty

    lo = max(pulled[0], selected[0])
    hi = min(pulled[1], selected[1])
    if lo > hi:
        return empty

    suggest_start = nodes[pulled[1]]
    suggest_end = ""
    if pulled[1] + 1 < len(nodes):
        suggest_end = nodes[-1]
    message = (
        f"Átfedés a már behúzott szakasszal: {nodes[lo]} → {nodes[hi]}. "
        f"Javasolt új start: {suggest_start}"
        + (f", javasolt vég: {suggest_end}" if suggest_end else "")
        + " (folytatás a megállás után)."
    )
    return OverlapAdvice(
        True,
        nodes[pulled[0]],
        nodes[pulled[1]],
        nodes[selected[0]],
        nodes[selected[1]],
        nodes[lo],
        nodes[hi],
        suggest_start,
        suggest_end,
        message,
    )


def live_route_preview_html(
    route: str,
    *,
    pulled_start: str = "",
    pulled_end: str = "",
    selected_start: str = "",
    selected_end: str = "",
    status_label: str = "",
) -> str:
    """Self-contained HTML+JS preview: live highlight while typing start/end."""
    payload = {
        "route": str(route or ""),
        "pulledStart": str(pulled_start or ""),
        "pulledEnd": str(pulled_end or ""),
        "start": str(selected_start or ""),
        "end": str(selected_end or ""),
        "status": str(status_label or ""),
    }
    data = json.dumps(payload, ensure_ascii=False)
    return f"""
<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>
  body {{ margin:0; font-family:Segoe UI,sans-serif; background:#0f172a; color:#e2e8f0; }}
  .wrap {{ padding:12px 14px; border:1px solid #334155; border-radius:10px; }}
  .legend span {{ display:inline-block; margin-right:10px; margin-bottom:6px; padding:2px 8px;
                  border-radius:4px; font-size:11px; font-weight:700; color:#0f172a; }}
  .pulled {{ background:#fb923c; }}
  .selected {{ background:#38bdf8; }}
  .overlap {{ background:#f43f5e; }}
  .route {{ font-family:Consolas,monospace; font-size:13px; line-height:1.85; white-space:pre-wrap;
            word-break:break-word; min-height:120px; max-height:280px; overflow:auto;
            background:#020617; border:1px solid #1e293b; border-radius:8px; padding:10px; margin-top:8px; }}
  .row {{ display:flex; gap:10px; margin-top:10px; flex-wrap:wrap; }}
  .field {{ flex:1; min-width:160px; }}
  label {{ display:block; font-size:11px; color:#94a3b8; margin-bottom:4px; text-transform:uppercase; }}
  input {{ width:100%; box-sizing:border-box; background:#1e293b; border:1px solid #475569; color:#f8fafc;
           border-radius:6px; padding:8px 10px; font-family:Consolas,monospace; }}
  input:focus {{ outline:none; border-color:#38bdf8; }}
  .msg {{ margin-top:10px; font-size:13px; padding:8px 10px; border-radius:6px; display:none; }}
  .msg.warn {{ display:block; background:#88133733; border:1px solid #f43f5e88; color:#fecdd3; }}
  .msg.ok {{ display:block; background:#0f766e33; border:1px solid #2dd4bf55; color:#99f6e4; }}
  .suggest {{ margin-top:8px; display:flex; gap:8px; flex-wrap:wrap; }}
  button {{ background:#334155; color:#e2e8f0; border:1px solid #64748b; border-radius:6px;
            padding:6px 10px; cursor:pointer; font-size:12px; }}
  button:hover {{ background:#475569; }}
  .status {{ font-size:12px; color:#94a3b8; margin-bottom:6px; }}
</style></head>
<body>
<div class="wrap">
  <div class="status" id="status"></div>
  <div class="legend">
    <span class="pulled">Már behúzva</span>
    <span class="selected">Most megadott</span>
    <span class="overlap">Átfedés</span>
  </div>
  <div class="route" id="routeView"></div>
  <div class="row">
    <div class="field">
      <label>Startpont (élő)</label>
      <input id="startIn" autocomplete="off" spellcheck="false"/>
    </div>
    <div class="field">
      <label>Végpont (élő)</label>
      <input id="endIn" autocomplete="off" spellcheck="false"/>
    </div>
  </div>
  <div class="msg" id="msg"></div>
  <div class="suggest" id="suggest"></div>
</div>
<script>
const DATA = {data};

function parseRoute(text) {{
  const nodes = [];
  const distances = [];
  const cleaned = String(text || "").trim();
  if (!cleaned) return {{ nodes, distances, tokens: [] }};
  const tokens = cleaned.replace(/\\n/g, " ").match(/\\S+(?:\\s+\\([^)]*\\))?/g) || [];
  const nodeParts = cleaned.replace(/\\([^)]+\\)/g, "|").split("|").map(s => s.trim()).filter(Boolean);
  const distParts = cleaned.match(/\\([^)]+\\)/g) || [];
  for (const d of distParts) {{
    const m = String(d).match(/[\\d]+([,.][\\d]+)?/);
    distances.push(m ? parseFloat(m[0].replace(",", ".")) : 0);
  }}
  return {{ nodes: nodeParts, distances, tokens }};
}}

function orderedSpan(nodes, a, b) {{
  a = String(a || "").trim();
  b = String(b || "").trim();
  if (!a || !b) return null;
  const i = nodes.indexOf(a);
  const j = nodes.indexOf(b);
  if (i < 0 || j < 0) return null;
  return i <= j ? [i, j] : [j, i];
}}

function esc(s) {{
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}}

function render() {{
  const start = document.getElementById("startIn").value.trim();
  const end = document.getElementById("endIn").value.trim();
  const {{ nodes, tokens }} = parseRoute(DATA.route);
  const pulled = orderedSpan(nodes, DATA.pulledStart, DATA.pulledEnd);
  const selected = orderedSpan(nodes, start, end);
  const roles = nodes.map(() => "plain");
  if (pulled) for (let i = pulled[0]; i <= pulled[1]; i++) roles[i] = "pulled";
  if (selected) for (let i = selected[0]; i <= selected[1]; i++) roles[i] = roles[i] === "pulled" ? "overlap" : "selected";

  const colors = {{ pulled: "#fb923c", selected: "#38bdf8", overlap: "#f43f5e" }};
  let html = "";
  if (tokens.length === nodes.length && tokens.length) {{
    html = tokens.map((t, i) => {{
      const role = roles[i] || "plain";
      if (role === "plain") return esc(t);
      return `<mark style="background:${{colors[role]}};color:#0f172a;font-weight:700;padding:2px 4px;border-radius:4px;">${{esc(t)}}</mark>`;
    }}).join(" ");
  }} else {{
    html = esc(DATA.route);
  }}
  document.getElementById("routeView").innerHTML = html || "<span style='color:#64748b'>—</span>";

  const msg = document.getElementById("msg");
  const suggest = document.getElementById("suggest");
  suggest.innerHTML = "";
  msg.className = "msg";
  msg.style.display = "none";
  msg.textContent = "";

  if (!pulled || !selected) {{
    if (start && end && !selected) {{
      msg.className = "msg warn";
      msg.style.display = "block";
      msg.textContent = "A start vagy végpont nincs a nyomvonalon.";
    }}
    return;
  }}
  const lo = Math.max(pulled[0], selected[0]);
  const hi = Math.min(pulled[1], selected[1]);
  if (lo > hi) {{
    msg.className = "msg ok";
    msg.style.display = "block";
    msg.textContent = "Nincs átfedés a már behúzott szakasszal.";
    return;
  }}
  const suggestStart = nodes[pulled[1]];
  const suggestEnd = pulled[1] + 1 < nodes.length ? nodes[nodes.length - 1] : "";
  msg.className = "msg warn";
  msg.style.display = "block";
  msg.textContent = `Átfedés: ${{nodes[lo]}} → ${{nodes[hi]}}. Javasolt start: ${{suggestStart}}` +
    (suggestEnd ? `, javasolt vég: ${{suggestEnd}}` : "") + ".";

  const b1 = document.createElement("button");
  b1.textContent = "Javasolt start: " + suggestStart;
  b1.onclick = () => {{ document.getElementById("startIn").value = suggestStart; render(); }};
  suggest.appendChild(b1);
  if (suggestEnd) {{
    const b2 = document.createElement("button");
    b2.textContent = "Javasolt vég: " + suggestEnd;
    b2.onclick = () => {{ document.getElementById("endIn").value = suggestEnd; render(); }};
    suggest.appendChild(b2);
  }}
  const b3 = document.createElement("button");
  b3.textContent = "Mindkét javaslat";
  b3.onclick = () => {{
    document.getElementById("startIn").value = suggestStart;
    if (suggestEnd) document.getElementById("endIn").value = suggestEnd;
    render();
  }};
  suggest.appendChild(b3);
}}

document.getElementById("status").textContent = DATA.status || "";
document.getElementById("startIn").value = DATA.start || "";
document.getElementById("endIn").value = DATA.end || "";
document.getElementById("startIn").addEventListener("input", render);
document.getElementById("endIn").addEventListener("input", render);
render();
</script>
</body></html>
"""


def calculate_pulled_length(
    route: str,
    node_a: str,
    allow_a: float,
    node_e: str,
    allow_e: float,
    start: str,
    end: str,
) -> CalcResult:
    route = str(route or "").strip()
    start = str(start or "").strip()
    end = str(end or "").strip()
    node_a = str(node_a or "").strip()
    node_e = str(node_e or "").strip()
    if not route or not start or not end:
        return CalcResult(False, error="Hiba: A nyomvonal, a startpont és a végpont megadása kötelező!")

    nodes, distances = parse_route(route)
    try:
        start_idx = nodes.index(start)
        end_idx = nodes.index(end)
    except ValueError:
        return CalcResult(False, error="Hiba: A megadott Startpont vagy Végpont nem található a nyomvonalban!")

    if start_idx > end_idx:
        start_idx, end_idx = end_idx, start_idx

    total = 0.0
    for i in range(start_idx, end_idx):
        if i < len(distances):
            total += distances[i]

    if start == node_a or end == node_a:
        total += float(allow_a or 0)
    if start == node_e or end == node_e:
        total += float(allow_e or 0)
    return CalcResult(True, meters=total)
