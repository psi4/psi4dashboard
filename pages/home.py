"""Home landing page: summary graphs of the Psi4 test data, served at /."""

import dash
from dash import Input, Output, callback, dcc, html

import callbacks
from components import graphs_container, page_ids
from data import get_scf_iteration_segments, get_timing_wall_time_segments

dash.register_page(__name__, path="/", name="Home")

IDS = page_ids("home", "url", "graphs")

# The green from the theme's COLORWAY; every SCF-iteration segment is painted this
# so the stepped line reads as a single series rather than one color per range.
SEGMENT_COLOR = "#6cb670"


def layout(**kwargs):
    # No interactive controls, so the summary cards are filled by the callback
    # below (keyed off the Location, which fires on page load), mirroring the SCF
    # page. More summary graphs can be appended to the returned list later.
    return html.Div(
        children=[
            dcc.Location(id=IDS.url, refresh=False),
            html.H2("Overview"),
            graphs_container(IDS.graphs),
        ]
    )


def segment_card(heading, segments, y):
    """Build one summary card from a ``get_version_segments`` frame.

    One line per minor-version range, each summed over the tests common to that
    range, so the total stays comparable within a line. Every segment is painted
    the same green (and the legend dropped) so the stepped series reads as one
    line rather than one color per range.
    """
    color_map = {segment: SEGMENT_COLOR for segment in segments["segment"].unique()}
    return callbacks.graph_group(
        heading,
        segments,
        y,
        color="segment",
        color_map=color_map,
        show_legend=False,
        y_baseline=False,
    )


@callback(
    Output(IDS.graphs, "children"),
    Input(IDS.url, "pathname"),
)
def update_graphs(pathname):
    specs = [
        ("Total SCF iterations across all tests", get_scf_iteration_segments(), "iterations"),
        ("Total wall time across all tests (seconds)", get_timing_wall_time_segments(), "wall_time"),
    ]
    cards = [
        segment_card(heading, segments, y)
        for heading, segments, y in specs
        if segments is not None and not segments.empty
    ]
    if not cards:
        return html.P("No summary data available.")
    return cards
