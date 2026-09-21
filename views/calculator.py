from __future__ import annotations

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.length_calc import (
    STATUS_COMPLETE,
    STATUS_NONE,
    STATUS_PARTIAL,
    analyze_overlap,
    cable_pull_status,
    cable_status_message,
    calculate_pulled_length,
    format_meters,
    latest_pull_ends,
    live_route_preview_html,
    parse_route,
)
from src.stutzen_filter import cable_route
from src.ui import copy_to_clipboard_button


def _num(value, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "<na>", "none"} else text


def _route_ends(row: pd.Series) -> tuple[str, str]:
    route = cable_route(row)
    nodes, _ = parse_route(route)
    a = _text(row.get("Knoten_A")) or _text(row.get("Point_A"))
    e = _text(row.get("Knoten_E")) or _text(row.get("Point_E"))
    if not a and nodes:
        a = nodes[0]
    if not e and nodes:
        e = nodes[-1]
    return a, e


def _apply_query_sync() -> None:
    """HTML élő előnézet → Streamlit mezők (query param bridge)."""
    params = st.query_params
    start = params.get("calc_live_start")
    end = params.get("calc_live_end")
    if start is None and end is None:
        return
    if start is not None:
        st.session_state["calc_start"] = str(start)
    if end is not None:
        st.session_state["calc_end"] = str(end)
    for key in ("calc_live_start", "calc_live_end"):
        try:
            del params[key]
        except Exception:
            pass


def _fill_from_cable(row: pd.Series) -> None:
    status = cable_pull_status(row)
    route = cable_route(row)
    node_a, node_e = _route_ends(row)
    st.session_state["calc_route"] = route
    st.session_state["calc_node_a"] = node_a
    st.session_state["calc_node_e"] = node_e
    st.session_state["calc_allow_a"] = _num(row.get("Aln_A"))
    st.session_state["calc_allow_e"] = _num(row.get("Aln_E"))
    st.session_state["calc_cable_status"] = status
    st.session_state["calc_status_msg"] = cable_status_message(row)
    # Start / vég mezőket ne töltse ki — a felhasználó adja meg.
    st.session_state["calc_start"] = ""
    st.session_state["calc_end"] = ""
    st.session_state["calc_focus_start"] = True

    if status == STATUS_COMPLETE:
        st.session_state["calc_pulled_start"] = node_a
        st.session_state["calc_pulled_end"] = node_e
    elif status == STATUS_PARTIAL:
        start, end = latest_pull_ends(row)
        st.session_state["calc_pulled_start"] = start
        st.session_state["calc_pulled_end"] = end
    else:
        st.session_state["calc_pulled_start"] = ""
        st.session_state["calc_pulled_end"] = ""


def _reset_form() -> None:
    for key, value in (
        ("calc_route", ""),
        ("calc_node_a", ""),
        ("calc_allow_a", 0.0),
        ("calc_node_e", ""),
        ("calc_allow_e", 0.0),
        ("calc_start", ""),
        ("calc_end", ""),
        ("calc_pulled_start", ""),
        ("calc_pulled_end", ""),
        ("calc_cable_status", ""),
        ("calc_status_msg", ""),
    ):
        st.session_state[key] = value
    st.session_state.pop("calc_result", None)
    st.session_state.pop("calc_focus_start", None)


def _focus_start_field() -> None:
    """Focus the Streamlit Startpont input after fill-from-cable."""
    components.html(
        """
        <script>
        (function() {
          const root = window.parent.document;
          const blocks = root.querySelectorAll('[data-testid="stTextInput"]');
          let target = null;
          for (const block of blocks) {
            const label = block.querySelector('label, p');
            const text = (label && label.textContent || '').trim();
            if (text.includes('Startpont (behúzott szakasz kezdete)')) {
              target = block.querySelector('input');
              break;
            }
          }
          if (target) {
            target.focus();
            try { target.select(); } catch (e) {}
            target.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        })();
        </script>
        """,
        height=0,
    )


def _live_html_with_sync(route: str, pulled_start: str, pulled_end: str, start: str, end: str, status: str) -> str:
    base = live_route_preview_html(
        route,
        pulled_start=pulled_start,
        pulled_end=pulled_end,
        selected_start=start,
        selected_end=end,
        status_label=status,
    )
    # Inject sync-to-Streamlit via query params (parent navigation).
    bridge = """
<script>
(function() {
  function syncToStreamlit() {
    const start = document.getElementById("startIn").value.trim();
    const end = document.getElementById("endIn").value.trim();
    try {
      const url = new URL(window.top.location.href);
      url.searchParams.set("calc_live_start", start);
      url.searchParams.set("calc_live_end", end);
      window.top.location.href = url.toString();
    } catch (err) {
      alert("Nem sikerült átadni a mezőket. Másold manuálisan a Start/Vég mezőkbe.");
    }
  }
  const bar = document.createElement("div");
  bar.style.marginTop = "10px";
  const btn = document.createElement("button");
  btn.textContent = "Átveszem a számoló mezőkbe";
  btn.onclick = syncToStreamlit;
  bar.appendChild(btn);
  const hint = document.createElement("div");
  hint.style.cssText = "font-size:11px;color:#94a3b8;margin-top:6px;";
  hint.textContent = "Gépelés közben azonnal színez — Enter nélkül. A számoláshoz vedd át a mezőkbe.";
  const wrap = document.querySelector(".wrap");
  if (wrap) { wrap.appendChild(bar); wrap.appendChild(hint); }
})();
</script>
"""
    return base.replace("</body></html>", bridge + "</body></html>")


def render() -> None:
    _apply_query_sync()

    st.title("Hossz kalkulátor")
    st.caption(
        "Részlegesen behúzott kábelhossz a nyomvonal szakaszai és a ráhagyások alapján. "
        "Ugyanaz a számítás, mint a kábelhúzás kalkulátorban."
    )

    for key, value in (
        ("calc_route", ""),
        ("calc_node_a", ""),
        ("calc_allow_a", 0.0),
        ("calc_node_e", ""),
        ("calc_allow_e", 0.0),
        ("calc_start", ""),
        ("calc_end", ""),
        ("calc_pulled_start", ""),
        ("calc_pulled_end", ""),
        ("calc_cable_status", ""),
        ("calc_status_msg", ""),
    ):
        st.session_state.setdefault(key, value)

    df = st.session_state.get("joined")
    if df is not None and not df.empty:
        ids = df["Kabelnr"].astype(str).tolist() if "Kabelnr" in df.columns else []
        if ids:
            st.subheader("Kábel betöltése")
            picked = st.selectbox("Kábel a feltöltött listából", ids, key="calc_cable_id")
            if st.button("Mezők kitöltése ebből a kábelből"):
                row = df.loc[df["Kabelnr"].astype(str).eq(picked)].iloc[0]
                _fill_from_cable(row)
                st.rerun()

    status_msg = st.session_state.get("calc_status_msg") or ""
    status = st.session_state.get("calc_cable_status") or ""
    if status_msg:
        if status == STATUS_COMPLETE:
            st.success(status_msg)
        elif status == STATUS_PARTIAL:
            st.warning(status_msg)
        elif status == STATUS_NONE:
            st.info(status_msg)

    st.subheader("Nyomvonal és végpontok")
    st.text_area(
        "Nyomvonal (teljes lánc)",
        placeholder="Pl.: 3E2004 (E 3,1) 3E2005 ... 1E3206",
        key="calc_route",
        height=244,
    )

    a1, a2 = st.columns(2)
    with a1:
        st.text_input('"A" végpont neve', placeholder="Pl.: 3E2004", key="calc_node_a")
        st.text_input('"E" végpont neve', placeholder="Pl.: 1E3206", key="calc_node_e")
        st.text_input("Startpont (behúzott szakasz kezdete)", placeholder="Pl.: 1E3206", key="calc_start")
        if st.session_state.pop("calc_focus_start", False):
            _focus_start_field()
        copy_to_clipboard_button(
            st.session_state.get("calc_start") or "",
            key="calc_copy_start",
            label="Startpont másolása",
        )
    with a2:
        st.number_input('"A" ráhagyás (m)', step=0.1, format="%.1f", key="calc_allow_a")
        st.number_input('"E" ráhagyás (m)', step=0.1, format="%.1f", key="calc_allow_e")
        st.text_input("Végpont (behúzott szakasz vége)", placeholder="Pl.: 3EDV205", key="calc_end")
        copy_to_clipboard_button(
            st.session_state.get("calc_end") or "",
            key="calc_copy_end",
            label="Végpont másolása",
        )

    route = st.session_state.get("calc_route") or ""
    start = st.session_state.get("calc_start") or ""
    end = st.session_state.get("calc_end") or ""
    pulled_start = st.session_state.get("calc_pulled_start") or ""
    pulled_end = st.session_state.get("calc_pulled_end") or ""

    if route:
        st.markdown("**Nyomvonal előnézet (élő kiemelés)**")
        components.html(
            _live_html_with_sync(route, pulled_start, pulled_end, start, end, status_msg),
            height=520,
            scrolling=True,
        )

        advice = analyze_overlap(route, pulled_start, pulled_end, start, end)
        if advice.has_overlap:
            st.error(advice.message)
            b1, b2, b3 = st.columns(3)
            with b1:
                if advice.suggest_start and st.button(
                    f"Start → {advice.suggest_start}", key="calc_apply_suggest_start"
                ):
                    st.session_state["calc_start"] = advice.suggest_start
                    st.rerun()
            with b2:
                if advice.suggest_end and st.button(
                    f"Vég → {advice.suggest_end}", key="calc_apply_suggest_end"
                ):
                    st.session_state["calc_end"] = advice.suggest_end
                    st.rerun()
            with b3:
                if advice.suggest_start and st.button("Mindkét javaslat", key="calc_apply_suggest_both"):
                    st.session_state["calc_start"] = advice.suggest_start
                    if advice.suggest_end:
                        st.session_state["calc_end"] = advice.suggest_end
                    st.rerun()
        elif pulled_start and pulled_end and start and end:
            st.caption("Nincs átfedés a már behúzott (narancs) és a most megadott (kék) szakasz között.")

    c1, c2 = st.columns([2, 1])
    with c1:
        calculate = st.button("Számítás", type="primary")
    with c2:
        reset = st.button("Reset")

    if reset:
        _reset_form()
        st.rerun()

    if calculate:
        result = calculate_pulled_length(
            st.session_state["calc_route"],
            st.session_state["calc_node_a"],
            float(st.session_state["calc_allow_a"] or 0),
            st.session_state["calc_node_e"],
            float(st.session_state["calc_allow_e"] or 0),
            st.session_state["calc_start"],
            st.session_state["calc_end"],
        )
        st.session_state["calc_result"] = result

    result = st.session_state.get("calc_result")
    if result is None:
        st.metric("Összesen behúzott kábelhossz", "0,0 m")
        return
    if not result.ok:
        st.error(result.error)
        st.metric("Összesen behúzott kábelhossz", "0,0 m")
        return
    st.metric("Összesen behúzott kábelhossz", format_meters(result.meters))
