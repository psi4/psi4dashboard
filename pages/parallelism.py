"""Parallelism page: wall-time- and speedup-vs-cores charts per timer, served at /parallelism."""

import dash
from dash import Input, Output, State, callback, dcc, html

import callbacks
from components import (
    graphs_container,
    level_slider,
    option_tabs,
    page_ids,
    resolve_level,
    select_dropdown,
)
from data import get_parallelism_levels, get_parallelism_tests, get_parallelism_versions

IDS = page_ids("parallelism", "url", "slider", "version", "test", "metrics", "graphs")

METRICS = ["wall_time", "speedup"]


def layout(level=None, version=None, test_name=None, **kwargs):
    """Build the page layout, seeding the controls from the URL query string.

    The version selection gates the test dropdown, so a shared link restores the
    version, its test, and the slider position together.
    """
    versions = get_parallelism_versions()
    sel_version = version if version in versions else (versions[-1] if versions else None)
    tests = get_parallelism_tests(sel_version)
    sel_test = test_name if test_name in tests else (tests[0] if tests else None)
    levels, sel_level = resolve_level(level, get_parallelism_levels())
    return html.Div(
        children=[
            dcc.Location(id=IDS.url, refresh=False),
            html.H2("Parallelism Dashboard"),
            level_slider(IDS.slider, levels, sel_level),
            select_dropdown(
                IDS.version,
                [{"label": v, "value": v} for v in versions],
                sel_version,
                "Select a version",
            ),
            select_dropdown(
                IDS.test,
                [{"label": t, "value": t} for t in tests],
                sel_test,
                "Select a test",
            ),
            option_tabs(IDS.metrics, METRICS),
            graphs_container(IDS.graphs),
        ]
    )


@callback(
    Output(IDS.test, "options"),
    Output(IDS.test, "value"),
    Input(IDS.version, "value"),
    State(IDS.test, "value"),
    prevent_initial_call=True,
)
def update_tests(version, current):
    return callbacks.parallelism_tests(version, current)


@callback(
    Output(IDS.url, "search"),
    Input(IDS.slider, "value"),
    Input(IDS.version, "value"),
    Input(IDS.test, "value"),
    prevent_initial_call=True,
)
def update_url_query(level, version, test):
    return callbacks.parallelism_url_query(level, version, test)


@callback(
    Output(IDS.graphs, "children"),
    Input(IDS.version, "value"),
    Input(IDS.test, "value"),
    Input(IDS.metrics, "value"),
    Input(IDS.slider, "value"),
)
def update_graphs(version, test, metric, level):
    plots = callbacks.parallelism_plots(test, version, level)
    line_weights = None
    if metric == "speedup":
        # Child speedups don't sum to the parent's, so a stacked-area breakdown
        # would be misleading — draw a breakdown as one line per child instead,
        # weighting every line on the page by its 1-core wall time (normalized
        # page-wide) so the timers that dominate the run read heaviest.
        line_weights = callbacks.speedup_line_weights(plots)
        plots = [(heading, df, False, color) for heading, df, _, color in plots]
    return callbacks.update_graphs(
        plots,
        metric,
        x="cores",
        hover_data=["n_calls", "wall_time"],
        heading_style=callbacks.NESTED_STYLE,
        line_weights=line_weights,
        ref_line=(metric=="speedup"),
    )


dash.register_page(__name__, path="/parallelism", name="Parallelism", layout=layout)
