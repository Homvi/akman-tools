"""Deprecated alias — use src.stutzen_filter and src.length_calc."""
from src.length_calc import calculate_pulled_length, parse_route
from src.stutzen_filter import filter_by_nodes, stutzen_filename

parse_route_distances = parse_route
filter_cables_by_stuetzen = filter_by_nodes
stuetzen_export_filename = stutzen_filename

__all__ = [
    "calculate_pulled_length",
    "parse_route_distances",
    "filter_cables_by_stuetzen",
    "stuetzen_export_filename",
]
