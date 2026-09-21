from __future__ import annotations

from src.analysis import (
    PULL_NOT,
    PULL_PARTIAL,
    PULL_YES,
    aggregate_stops,
    apply_filters,
    available_categories,
    stopped_by_location,
    unique_devices,
)
from src.export import catra_list_xlsx, kurzliste_xlsx
from src.pathways import annotate_paths, cables_stopped_at, route_groups, unique_stop_stuetzen

_CACHE_KEYS = (
    "_filter_options",
    "_opts_sig",
    "_filtered_cache",
    "_groups_cache",
    "_xlsx_cache",
    "_stop_cache",
    "_events_cache",
)


def clear_runtime_caches() -> None:
    try:
        import streamlit as st
    except ImportError:
        return
    for key in _CACHE_KEYS:
        st.session_state.pop(key, None)


def _session():
    import streamlit as st

    return st.session_state


def current_filter_key() -> tuple:
    state = _session()
    pulled = []
    if state.get("pull_not"):
        pulled.append(PULL_NOT)
    if state.get("pull_partial"):
        pulled.append(PULL_PARTIAL)
    if state.get("pull_yes"):
        pulled.append(PULL_YES)
    return (
        tuple(state.get("filter_devices") or []),
        tuple(pulled),
        tuple(state.get("filter_thickness") or []),
        state.get("filter_category") or "All",
        tuple(state.get("filter_stop_stuetzen") or []),
    )


def ensure_enriched(df):
    if {"Path_nodes", "Stop_locations", "Pull_status"}.issubset(df.columns):
        return df
    enriched = annotate_paths(df)
    state = _session()
    if state.get("joined") is df:
        state["joined"] = enriched
    return enriched


def filter_options(df) -> dict:
    state = _session()
    sig = state.get("data_signature")
    if state.get("_opts_sig") == sig and "_filter_options" in state:
        return state["_filter_options"]
    annotated = ensure_enriched(df)
    options = {
        "devices": unique_devices(annotated),
        "categories": available_categories(annotated),
        "stop_stuetzen": unique_stop_stuetzen(annotated),
    }
    state["_filter_options"] = options
    state["_opts_sig"] = sig
    return options


def get_filtered(df, *, ignore_pull: bool = False):
    state = _session()
    devices, pulled, thickness, category, stops = current_filter_key()
    if ignore_pull:
        pulled = ()
    key = (state.get("data_signature"), (devices, pulled, thickness, category, stops))
    cache = state.setdefault("_filtered_cache", {})
    if key in cache:
        return cache[key]
    annotated = ensure_enriched(df)
    out = apply_filters(
        annotated,
        devices=list(devices) or None,
        pulled=list(pulled) or None,
        thickness=list(thickness) or None,
        categories=None if category == "All" else [category],
    )
    if stops:
        out = cables_stopped_at(out, list(stops))
    if len(cache) >= 8:
        cache.pop(next(iter(cache)))
    cache[key] = out
    return out


def get_route_groups(view, *, mode: str, min_size: int, similarity: float):
    state = _session()
    key = (state.get("data_signature"), current_filter_key(), mode, min_size, similarity)
    cache = state.setdefault("_groups_cache", {})
    if key in cache:
        return cache[key]
    groups = route_groups(view, mode=mode, min_size=min_size, similarity=similarity)
    cache.clear()
    cache[key] = groups
    return groups


def get_stop_tables(view):
    state = _session()
    key = (state.get("data_signature"), current_filter_key(), "active_stop_v1")
    cache = state.setdefault("_stop_cache", {})
    if key in cache:
        return cache[key]
    detail = stopped_by_location(view)
    summary = aggregate_stops(detail)
    cache.clear()
    cache[key] = (detail, summary)
    return detail, summary


def cached_export_xlsx(cache_key, cables, header=None, *, kind: str = "catra") -> bytes:
    state = _session()
    cache = state.setdefault("_xlsx_cache", {})
    cache_key = (cache_key, kind, "export2")
    if cache_key in cache:
        return cache[cache_key]
    if kind == "kurz":
        data = kurzliste_xlsx(cables)
    else:
        data = catra_list_xlsx(cables, header)
    if len(cache) >= 24:
        cache.pop(next(iter(cache)))
    cache[cache_key] = data
    return data


def cached_catra_xlsx(cache_key, cables, header) -> bytes:
    return cached_export_xlsx(cache_key, cables, header, kind="catra")
