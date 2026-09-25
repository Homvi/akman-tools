from __future__ import annotations

import streamlit as st

from src.ui import render_uploads
from views.all_cables import render as render_all_cables
from views.calculator import render as render_calculator
from views.guide import render as render_guide
from views.id_export import render as render_id_export
from views.progress import render as render_progress
from views.routes import render as render_routes
from views.stopped import render as render_stopped
from views.stutzen import render as render_stutzen
from views.workforce import render as render_workforce

st.set_page_config(page_title="Cable installation", layout="wide")
render_uploads()

pages = {
    "cables": st.Page(render_all_cables, title="All cables", url_path="cables", default=True),
    "stopped": st.Page(render_stopped, title="Stopped cables", url_path="stopped"),
    "stutzen": st.Page(render_stutzen, title="Stütze / Bahn szűrő", url_path="stutzen"),
    "id_export": st.Page(render_id_export, title="Cable ID export", url_path="id-export"),
    "workforce": st.Page(render_workforce, title="Workforce", url_path="workforce"),
    "routes": st.Page(render_routes, title="Nyomvonal-csoportok", url_path="routes"),
    "progress": st.Page(render_progress, title="Progress", url_path="progress"),
    "calculator": st.Page(render_calculator, title="Hossz kalkulátor", url_path="calculator"),
    "guide": st.Page(render_guide, title="Hogyan működik", url_path="guide"),
}
st.session_state["_pages"] = pages
st.navigation(list(pages.values())).run()
