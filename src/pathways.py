from __future__ import annotations

import re
from collections import defaultdict
from functools import lru_cache

import pandas as pd

from src.analysis import PULL_NOT, PULL_PARTIAL, assign_pull_status
from src.categories import CAT_LABELS

_SPLIT_DIST = re.compile(r"\s*\([^)]*\)\s*")
_POINT = re.compile(r"^[0-9]+[A-Z]+[0-9]+(?:\.[0-9]+)?$", re.IGNORECASE)
_EMPTY = {"", "<NA>", "nan", "None"}
_IGNORE_NODES = {"KA", "KE", "RINGA", "RINGE", "RING"}

MODE_SIM = "90% nyomvonal-egyezés"
MODE_FULL_ST = "Teljes Stütze-sor"
MODE_AE = "A → E (ugyanonnan ugyanoda)"
MODE_ST2 = "2 azonos Stütze"
MODE_ST3 = "3 azonos Stütze"
MODE_ST4 = "4 azonos Stütze"
GROUP_MODES = (MODE_SIM, MODE_FULL_ST, MODE_AE, MODE_ST2, MODE_ST3, MODE_ST4)


@lru_cache(maxsize=8192)
def _parse_path_nodes_cached(text: str) -> tuple[str, ...]:
    nodes: list[str] = []
    for chunk in _SPLIT_DIST.split(text):
        for token in chunk.split():
            node = token.strip(" ,;|")
            if not node:
                continue
            if node.upper() in _IGNORE_NODES or node.upper().startswith("RING"):
                continue
            if not _POINT.match(node):
                continue
            nodes.append(node)
    return tuple(nodes)


def parse_path_nodes(pfad) -> list[str]:
    """Real Bahn points only. Drops distances, KA/KE, RingA/RingE."""
    if pfad is None or (isinstance(pfad, float) and pd.isna(pfad)):
        return []
    text = str(pfad).strip()
    if not text:
        return []
    return list(_parse_path_nodes_cached(text))


def is_stuetze(node: str) -> bool:
    upper = str(node).upper()
    return "EDV" in upper or "EDH" in upper


def extract_stuetzen(nodes: list[str]) -> list[str]:
    return [node for node in nodes if is_stuetze(node)]


def _clean_point(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if text in _EMPTY or text.upper() in _IGNORE_NODES or text.upper().startswith("RING"):
        return ""
    return text


_ANNOTATED_COLS = {"Path_nodes", "Point_A", "Point_E", "Stuetzen", "Pull_status"}


def _is_blank(value) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() in _EMPTY


def stop_locations_series(df: pd.DataFrame) -> pd.Series:
    buckets = [[] for _ in range(len(df))]
    for slot in (1, 2, 3):
        gcol = f"Gestoppt_{slot}"
        if gcol not in df.columns:
            continue
        stopped = df[gcol].notna().to_numpy()
        end = df[f"Endsegment_{slot}"] if f"Endsegment_{slot}" in df.columns else None
        start = df[f"Startsegment_{slot}"] if f"Startsegment_{slot}" in df.columns else None
        for i, flag in enumerate(stopped):
            if not flag:
                continue
            loc = None
            if end is not None and not _is_blank(end.iloc[i]):
                loc = str(end.iloc[i]).strip()
            elif start is not None and not _is_blank(start.iloc[i]):
                loc = str(start.iloc[i]).strip()
            if loc:
                buckets[i].append(loc)
    return pd.Series(buckets, index=df.index, dtype=object)


def annotate_paths(df: pd.DataFrame) -> pd.DataFrame:
    if _ANNOTATED_COLS.issubset(df.columns):
        if "Stop_locations" not in df.columns:
            out = df.copy()
            out["Stop_locations"] = stop_locations_series(out)
            return out
        return df
    out = assign_pull_status(df)
    if "Pfad" in out.columns:
        nodes = out["Pfad"].map(parse_path_nodes)
    else:
        nodes = pd.Series([[] for _ in range(len(out))], index=out.index)
    out["Path_nodes"] = nodes
    out["Stuetzen"] = nodes.map(extract_stuetzen)
    out["Point_A"] = out["Knoten_A"].map(_clean_point) if "Knoten_A" in out.columns else ""
    out["Point_E"] = out["Knoten_E"].map(_clean_point) if "Knoten_E" in out.columns else ""
    out["Stuetzen_text"] = out["Stuetzen"].map(lambda items: " → ".join(items))
    out["Stop_locations"] = stop_locations_series(out)
    return out


def ngrams(items: list[str], n: int) -> list[tuple[str, ...]]:
    if n < 1 or len(items) < n:
        return []
    return [tuple(items[i : i + n]) for i in range(len(items) - n + 1)]


def lcs_length(left, right) -> int:
    n, m = len(left), len(right)
    if n == 0 or m == 0:
        return 0
    prev = [0] * (m + 1)
    for i in range(1, n + 1):
        curr = [0] * (m + 1)
        token = left[i - 1]
        for j in range(1, m + 1):
            if token == right[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(curr[j - 1], prev[j])
        prev = curr
    return prev[m]


@lru_cache(maxsize=200_000)
def _similarity_cached(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    return lcs_length(left, right) / max(len(left), len(right))


def path_similarity(left, right, threshold: float | None = None) -> float:
    if not left or not right:
        return 0.0
    n, m = len(left), len(right)
    longest = n if n > m else m
    shortest = m if n > m else n
    if threshold is not None and shortest / longest < threshold:
        return 0.0
    return _similarity_cached(tuple(left), tuple(right))


def longest_common_prefix(paths: list[list[str]]) -> list[str]:
    if not paths:
        return []
    shortest = min(len(path) for path in paths)
    shared: list[str] = []
    for i in range(shortest):
        token = paths[0][i]
        if all(path[i] == token for path in paths):
            shared.append(token)
        else:
            break
    return shared


def cable_stop_locations(row: pd.Series) -> list[str]:
    locations = []
    for slot in (1, 2, 3):
        stopped = row.get(f"Gestoppt_{slot}")
        if pd.isna(stopped):
            continue
        location = row.get(f"Endsegment_{slot}")
        if pd.isna(location) or str(location).strip() in _EMPTY:
            location = row.get(f"Startsegment_{slot}")
        if pd.isna(location) or str(location).strip() in _EMPTY:
            continue
        locations.append(str(location).strip())
    return locations


def _stop_lists(df: pd.DataFrame) -> pd.Series:
    if "Stop_locations" in df.columns:
        return df["Stop_locations"]
    return stop_locations_series(df)


def unique_stop_locations(df: pd.DataFrame, *, stuetzen_only: bool = False) -> list[str]:
    found: set[str] = set()
    for items in _stop_lists(df):
        for location in items:
            if stuetzen_only and not is_stuetze(location):
                continue
            found.add(location)
    return sorted(found)


def unique_stop_stuetzen(df: pd.DataFrame) -> list[str]:
    return unique_stop_locations(df, stuetzen_only=True)


def cables_stopped_at(df: pd.DataFrame, locations: list[str]) -> pd.DataFrame:
    wanted = {str(item).strip().upper() for item in locations if str(item).strip()}
    if not wanted:
        return df
    mask = _stop_lists(df).map(lambda items: bool(wanted.intersection(loc.upper() for loc in items)))
    return df.loc[mask]


def _category_breakdown(part: pd.DataFrame) -> dict:
    length = pd.to_numeric(part.get("Length_m"), errors="coerce").fillna(0)
    cats = part["Category"] if "Category" in part.columns else pd.Series(["Unclassified"] * len(part), index=part.index)
    stats: dict = {"Total_m": float(length.sum())}
    extra = sorted({str(c) for c in cats.dropna().unique() if str(c) not in CAT_LABELS})
    for cat in list(CAT_LABELS) + extra:
        mask = cats.eq(cat)
        stats[f"{cat}_n"] = int(mask.sum())
        stats[f"{cat}_m"] = float(length[mask].sum())
    return stats


def _group_row(key_label: str, part: pd.DataFrame, extra: dict) -> dict:
    unpulled = part[part["Pull_status"].isin([PULL_NOT, PULL_PARTIAL])]
    row = {
        "Group": key_label,
        "Cable_count": len(part),
        "Unpulled_count": len(unpulled),
        "join_keys": tuple(part["join_key"].tolist()),
    }
    row.update(extra)
    row.update(_category_breakdown(part))
    return row


def _cluster_similar(annotated: pd.DataFrame, threshold: float) -> list[list]:
    usable = (
        annotated["Path_nodes"].map(bool)
        & annotated["Point_A"].astype(str).str.len().gt(0)
        & annotated["Point_E"].astype(str).str.len().gt(0)
    )
    work = annotated.loc[usable, ["Point_A", "Path_nodes"]]
    blocks: dict[str, dict[tuple[str, ...], list]] = defaultdict(lambda: defaultdict(list))
    for row in work.itertuples(index=True):
        blocks[str(row.Point_A)][tuple(row.Path_nodes)].append(row.Index)

    clusters: list[list] = []
    for path_map in blocks.values():
        paths = list(path_map)
        parent = {path: path for path in paths}

        def find(x, _parent=parent):
            while _parent[x] != x:
                _parent[x] = _parent[_parent[x]]
                x = _parent[x]
            return x

        def union(a, b, _parent=parent):
            ra, rb = find(a), find(b)
            if ra != rb:
                _parent[rb] = ra

        for i, left in enumerate(paths):
            for right in paths[i + 1 :]:
                if path_similarity(left, right, threshold) >= threshold:
                    union(left, right)

        grouped: dict[tuple[str, ...], list] = defaultdict(list)
        for path, indexes in path_map.items():
            grouped[find(path)].extend(indexes)
        clusters.extend(grouped.values())
    return clusters


def route_groups(
    df: pd.DataFrame,
    mode: str = MODE_SIM,
    min_size: int = 2,
    similarity: float = 0.9,
) -> pd.DataFrame:
    annotated = df if _ANNOTATED_COLS.issubset(df.columns) else annotate_paths(df)
    rows = []

    if mode == MODE_SIM:
        for indexes in _cluster_similar(annotated, similarity):
            part = annotated.loc[indexes]
            if len(part) < min_size:
                continue
            shared = longest_common_prefix(part["Path_nodes"].tolist())
            a = part["Point_A"].mode().iloc[0] if not part["Point_A"].mode().empty else ""
            e = part["Point_E"].mode().iloc[0] if not part["Point_E"].mode().empty else ""
            rows.append(
                _group_row(
                    f"{a} → {e}",
                    part,
                    {
                        "Point_A": a,
                        "Point_E": e,
                        "Stuetzen": " → ".join(shared[:12]),
                        "Match": f"{int(similarity * 100)}%+",
                    },
                )
            )
    else:
        buckets: dict[tuple, list] = {}
        cols = annotated[["Point_A", "Point_E", "Path_nodes", "Stuetzen"]]
        for row in cols.itertuples(index=True):
            if not row.Path_nodes or not row.Point_A or not row.Point_E:
                continue
            a, e = row.Point_A, row.Point_E
            if mode == MODE_FULL_ST:
                stuetzen = tuple(row.Stuetzen)
                if not stuetzen:
                    continue
                buckets.setdefault((a, e, stuetzen), []).append(row.Index)
            elif mode == MODE_AE:
                buckets.setdefault((a, e), []).append(row.Index)
            else:
                n = {MODE_ST2: 2, MODE_ST3: 3, MODE_ST4: 4}[mode]
                for gram in ngrams(row.Stuetzen, n):
                    buckets.setdefault(gram, []).append(row.Index)

        for key, indexes in buckets.items():
            part = annotated.loc[list(dict.fromkeys(indexes))]
            if len(part) < min_size:
                continue
            if mode == MODE_FULL_ST:
                a, e, seq = key
                extra = {"Point_A": a, "Point_E": e, "Stuetzen": " → ".join(seq), "Match": "100% Stütze"}
                label = f"{a} → {e}"
            elif mode == MODE_AE:
                a, e = key
                extra = {"Point_A": a, "Point_E": e, "Stuetzen": "", "Match": "A→E"}
                label = f"{a} → {e}"
            else:
                extra = {"Point_A": "", "Point_E": "", "Stuetzen": " → ".join(key), "Match": f"{len(key)} Stütze"}
                label = " → ".join(key)
            rows.append(_group_row(label, part, extra))

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["Cable_count", "Total_m"], ascending=[False, False]).reset_index(drop=True)


def cables_in_group(df: pd.DataFrame, join_keys: tuple | list) -> pd.DataFrame:
    part = df[df["join_key"].isin(join_keys)]
    if _ANNOTATED_COLS.issubset(part.columns):
        return part
    return annotate_paths(part)


def stop_groups(cables: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, cable in cables.iterrows():
        for location in cable_stop_locations(cable):
            rows.append({"Stop_location": location, "join_key": cable.get("join_key"), "Kabelnr": cable.get("Kabelnr")})
    if not rows:
        return pd.DataFrame(columns=["Stop_location", "Cable_count", "Cables", "join_keys"])
    detail = pd.DataFrame(rows)
    grouped = (
        detail.groupby("Stop_location", dropna=False)
        .agg(
            Cable_count=("join_key", "nunique"),
            Cables=("Kabelnr", lambda s: ", ".join(sorted({str(v) for v in s if pd.notna(v)}))),
            join_keys=("join_key", lambda s: tuple(s.dropna().unique())),
        )
        .reset_index()
        .sort_values("Cable_count", ascending=False)
    )
    return grouped[grouped["Cable_count"] >= 2].reset_index(drop=True)


def group_display_columns(groups: pd.DataFrame) -> list[str]:
    preferred = [
        "Group",
        "Match",
        "Point_A",
        "Point_E",
        "Stuetzen",
        "Cable_count",
        "Unpulled_count",
        "Total_m",
    ]
    cat_cols = [col for col in groups.columns if (col.endswith("_n") or col.endswith("_m")) and col != "Total_m"]
    return [col for col in preferred + cat_cols if col in groups.columns]
