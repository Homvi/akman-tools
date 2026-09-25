from __future__ import annotations

import hashlib
import html
import json
from datetime import date, datetime

import streamlit as st
import streamlit.components.v1 as components

from src.analysis import cable_numbers

from src.export import to_xlsx_bytes
from src.join import join_cable_data, unmatched_ids
from src.parsers import parse_catra_list, parse_status_list
from src.runtime import cached_export_xlsx, clear_runtime_caches, filter_options, get_filtered
from src.store import clear_dataset, clear_workforce, load_dataset, load_workforce, save_dataset, save_workforce
from src.workforce import parse_workforce_excel

FILTER_KEYS = (
    "filter_devices",
    "filter_pulled",
    "filter_thickness",
    "filter_categories",
    "filter_stop_stuetzen",
)
TABLE_COLS = [
    "Kabelnr",
    "Category",
    "Thickness",
    "Pull_status",
    "verlegt",
    "Length_m",
    "Remaining_m",
    "Total_teilgezogene_meter",
    "Liste",
    "Artikel",
    "Kabeltyp",
    "Kabeladern",
    "Geraet_A",
    "Geraet_E",
    "Startsegment_1",
    "Endsegment_1",
    "Gestoppt_1",
    "Bemerkung",
    "Pfad",
]


def ensure_auth() -> bool:
    return True


def init_filters() -> None:
    st.session_state.setdefault("filter_devices", [])
    st.session_state.setdefault("pull_not", False)
    st.session_state.setdefault("pull_partial", False)
    st.session_state.setdefault("pull_yes", False)
    st.session_state.setdefault("filter_thickness", [])
    st.session_state.setdefault("filter_category", "All")
    st.session_state.setdefault("filter_stop_stuetzen", [])


def clear_filters() -> None:
    st.session_state["filter_devices"] = []
    st.session_state["pull_not"] = False
    st.session_state["pull_partial"] = False
    st.session_state["pull_yes"] = False
    st.session_state["filter_thickness"] = []
    st.session_state["filter_category"] = "All"
    st.session_state["filter_stop_stuetzen"] = []


def _upload_signature(status_file, catra_file) -> str:
    digest = hashlib.sha256()
    digest.update(status_file.getvalue())
    digest.update(b"\0")
    digest.update(catra_file.getvalue())
    return digest.hexdigest()


def _clear_loaded_data() -> None:
    for key in (
        "joined",
        "only_status",
        "only_catra",
        "catra_header",
        "data_signature",
        "stop_zip",
        "status_name",
        "catra_name",
    ):
        st.session_state.pop(key, None)
    clear_runtime_caches()


def _apply_dataset(data: dict, *, persist: bool = False) -> None:
    st.session_state["joined"] = data["joined"]
    st.session_state["only_status"] = data["only_status"]
    st.session_state["only_catra"] = data["only_catra"]
    st.session_state["catra_header"] = data["header"]
    st.session_state["data_signature"] = data["signature"]
    st.session_state["status_name"] = data["status_name"]
    st.session_state["catra_name"] = data["catra_name"]
    if persist:
        try:
            save_dataset(
                joined=data["joined"],
                header=data["header"],
                only_status=data["only_status"],
                only_catra=data["only_catra"],
                status_name=data["status_name"],
                catra_name=data["catra_name"],
                signature=data["signature"],
            )
        except Exception as exc:
            st.sidebar.warning(f"Could not save local database: {exc}")


def _show_load_status() -> None:
    joined = st.session_state.get("joined")
    if joined is None:
        return
    status_name = st.session_state.get("status_name") or "Progressliste"
    catra_name = st.session_state.get("catra_name") or "CaTra"
    st.sidebar.success(f"{len(joined):,} cables — {status_name} + {catra_name}")
    only_status = st.session_state.get("only_status") or []
    only_catra = st.session_state.get("only_catra") or []
    if only_status:
        st.sidebar.caption(f"{len(only_status)} status IDs without CaTra match.")
    if only_catra:
        st.sidebar.caption(f"{len(only_catra)} CaTra IDs without status match.")


def _workforce_signature(upload) -> str:
    return hashlib.sha256(upload.getvalue()).hexdigest()


def _apply_workforce(data: dict) -> None:
    st.session_state["workforce"] = data["frame"]
    st.session_state["workforce_name"] = data["file_name"]
    st.session_state["workforce_signature"] = data["signature"]
    st.session_state["workforce_year"] = data["year"]
    st.session_state["workforce_saved_at"] = data.get("saved_at")


def _clear_workforce_state() -> None:
    for key in ("workforce", "workforce_name", "workforce_signature", "workforce_year", "workforce_saved_at"):
        st.session_state.pop(key, None)
    clear_workforce()


def _show_workforce_status() -> None:
    frame = st.session_state.get("workforce")
    if frame is None or getattr(frame, "empty", True):
        return
    name = st.session_state.get("workforce_name") or "workforce.xlsx"
    people = int(frame["Name"].nunique()) if "Name" in frame.columns else 0
    st.sidebar.success(f"Workforce: {name} · {people} people")


def render_uploads() -> None:
    if "joined" not in st.session_state:
        stored = load_dataset()
        if stored is not None:
            _apply_dataset(stored)

    if "workforce" not in st.session_state or st.session_state.get("workforce") is None:
        wf_stored = load_workforce()
        if wf_stored is not None:
            _apply_workforce(wf_stored)

    st.sidebar.header("Data files")
    st.sidebar.caption(
        "Upload Progressliste + CaTra once (required). "
        "Workforce hours Excel is optional — used on Workforce and weekly Progress."
    )
    status_file = st.sidebar.file_uploader("Status list (Progressliste)", type=["xlsx"], key="status_file")
    catra_file = st.sidebar.file_uploader("CaTra cable list", type=["xlsx"], key="catra_file")
    wf_year = st.sidebar.number_input(
        "Workforce year",
        min_value=2020,
        max_value=2100,
        value=int(st.session_state.get("workforce_year") or date.today().year),
        step=1,
        key="workforce_year_input",
        help="Calendar year for day columns in the workforce Excel.",
    )
    workforce_file = st.sidebar.file_uploader(
        "Workforce hours (optional)",
        type=["xlsx"],
        key="workforce_file",
        help="Name / position / daily hours sheets. H = holiday.",
    )

    if status_file and catra_file:
        signature = _upload_signature(status_file, catra_file)
        already = (
            st.session_state.get("data_signature") == signature
            and "joined" in st.session_state
            and "_block" in st.session_state["joined"].columns
        )
        if not already:
            status_file.seek(0)
            catra_file.seek(0)
            try:
                status = parse_status_list(status_file)
                catra = parse_catra_list(catra_file)
                joined = join_cable_data(status, catra)
                only_status, only_catra = unmatched_ids(status, catra)
            except Exception as exc:
                st.sidebar.error(f"Could not parse files: {exc}")
                return
            _apply_dataset(
                {
                    "joined": joined,
                    "header": list(catra.attrs.get("catra_header") or []),
                    "only_status": only_status,
                    "only_catra": only_catra,
                    "status_name": status_file.name,
                    "catra_name": catra_file.name,
                    "signature": signature,
                },
                persist=True,
            )
            st.session_state.pop("stop_zip", None)
            clear_runtime_caches()
        _show_load_status()
    elif "joined" in st.session_state:
        _show_load_status()
    else:
        stored = load_dataset()
        if stored is not None:
            _apply_dataset(stored)
            _show_load_status()

    if workforce_file is not None:
        wf_sig = _workforce_signature(workforce_file)
        already_wf = (
            st.session_state.get("workforce_signature") == wf_sig
            and st.session_state.get("workforce") is not None
        )
        if not already_wf:
            try:
                workforce_file.seek(0)
                frame = parse_workforce_excel(workforce_file, year=int(wf_year))
            except Exception as exc:
                st.sidebar.error(f"Could not parse workforce file: {exc}")
                frame = None
            if frame is not None:
                saved_at = datetime.now().isoformat(timespec="seconds")
                try:
                    save_workforce(
                        frame=frame,
                        file_name=workforce_file.name,
                        signature=wf_sig,
                        year=int(wf_year),
                    )
                except Exception as exc:
                    st.sidebar.warning(f"Could not save workforce locally: {exc}")
                _apply_workforce(
                    {
                        "frame": frame,
                        "file_name": workforce_file.name,
                        "signature": wf_sig,
                        "year": int(wf_year),
                        "saved_at": saved_at,
                    }
                )
    _show_workforce_status()

    if st.session_state.get("joined") is not None:
        if st.sidebar.button("Clear cable data", use_container_width=True):
            _clear_loaded_data()
            clear_dataset()
            st.rerun()
    if st.session_state.get("workforce") is not None:
        if st.sidebar.button("Clear workforce data", use_container_width=True):
            _clear_workforce_state()
            st.rerun()


def render_filters(df) -> None:
    init_filters()
    st.sidebar.header("Filters")
    options = filter_options(df)
    st.sidebar.multiselect("Device (Gerät)", options["devices"], key="filter_devices")
    st.sidebar.markdown("**Cable pulled?**")
    st.sidebar.checkbox("Not pulled", key="pull_not", help="Nincs Startsegment.")
    st.sidebar.checkbox("Részlegesen", key="pull_partial", help="Van Startsegment, de nincs verlegt dátum.")
    st.sidebar.checkbox("Pulled", key="pull_yes", help="Van verlegt dátum.")
    st.sidebar.multiselect("Thickness", ["Thin", "Thick", "Unknown"], key="filter_thickness")
    st.sidebar.selectbox(
        "Category",
        ["All"] + options["categories"],
        key="filter_category",
    )
    stop_stuetzen = options["stop_stuetzen"]
    if stop_stuetzen:
        st.sidebar.multiselect(
            "Megállva Stütze",
            stop_stuetzen,
            key="filter_stop_stuetzen",
            help="Csak azok a kábelek, amelyek Gestoppt Endsegmentje ez a Stütze (EDV/EDH).",
        )
    if st.sidebar.button("Remove all filters", use_container_width=True):
        clear_filters()
        st.rerun()


def filtered_frame(df):
    return get_filtered(df)


def visible_columns(df):
    return [col for col in TABLE_COLS if col in df.columns]


def download_button(df, label: str, filename: str) -> None:
    st.download_button(
        label,
        data=to_xlsx_bytes(df),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        disabled=df.empty,
    )


def _cable_export_fingerprint(cables) -> tuple:
    """Stable id of the cable set so export cache does not reuse another selection."""
    if cables is None or getattr(cables, "empty", True):
        return ()
    if "join_key" in cables.columns:
        return tuple(str(v) for v in cables["join_key"].tolist())
    if "Kabelnr" in cables.columns:
        return tuple(str(v) for v in cables["Kabelnr"].tolist())
    return (len(cables),)


def _lazy_cable_download(cables, filename: str, key: str, label: str, kind: str) -> None:
    header = st.session_state.get("catra_header") or None
    fingerprint = _cable_export_fingerprint(cables)
    cache_key = (st.session_state.get("data_signature"), key, kind, fingerprint)
    wrapped = (cache_key, kind, "export2")
    if wrapped not in st.session_state.get("_xlsx_cache", {}):
        if st.button(label, key=f"prep_{key}_{kind}_{hash(fingerprint) & 0xFFFFFFFF:x}", disabled=cables.empty):
            cached_export_xlsx(cache_key, cables, header, kind=kind)
            st.rerun()
    if wrapped in st.session_state.get("_xlsx_cache", {}):
        st.download_button(
            "Letöltés",
            data=cached_export_xlsx(cache_key, cables, header, kind=kind),
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_{key}_{kind}_{hash(fingerprint) & 0xFFFFFFFF:x}",
        )


def cable_export_buttons(cables, basename: str, key: str) -> None:
    left, right = st.columns(2)
    with left:
        _lazy_cable_download(
            cables,
            f"{basename}_huzokartya.xlsx",
            f"{key}_catra",
            "Húzókártya (CaTra)",
            "catra",
        )
    with right:
        _lazy_cable_download(
            cables,
            f"{basename}_kurzliste.xlsx",
            f"{key}_kurz",
            "Kurzliste",
            "kurz",
        )


def copy_to_clipboard_button(text: str, *, key: str, label: str = "Copy to clipboard") -> None:
    payload = json.dumps(text)
    button_id = html.escape(key, quote=True)
    components.html(
        f"""
        <button id="{button_id}" style="padding:6px 14px;cursor:pointer;border:1px solid #ccc;
            border-radius:6px;background:#f6f6f6;font-family:sans-serif;">
            {html.escape(label)}
        </button>
        <script>
        const btn = document.getElementById("{button_id}");
        const label = {json.dumps(label)};
        btn.addEventListener("click", async () => {{
            try {{
                await navigator.clipboard.writeText({payload});
                btn.textContent = "Másolva";
                setTimeout(() => {{ btn.textContent = label; }}, 1600);
            }} catch (err) {{
                btn.textContent = "Másold a listából";
            }}
        }});
        </script>
        """,
        height=46,
    )


def cable_number_copy_box(title: str, cables, *, key: str) -> None:
    numbers = cable_numbers(cables)
    text = ", ".join(numbers)
    st.subheader(title)
    st.caption(f"{len(numbers)} kábelszám, vesszővel elválasztva.")
    copy_to_clipboard_button(text, key=f"copy_{key}", label="Copy to clipboard")
    st.code(text or "—", language=None)
