"""Timers page: line charts of a selected timer's metrics across tests, served at /timers."""

import dash
from dash import Input, Output, State, callback, dcc, html

import callbacks
from components import (
    METRICS,
    graphs_container,
    level_slider,
    option_tabs,
    page_ids,
    resolve_level,
    select_dropdown,
)

IDS = page_ids("timers", "url", "slider", "dropdown", "metrics", "graphs")


def layout(level=None, **kwargs):
    """Build the page layout, seeding the slider and dropdown from the URL.

    ``level`` and the dropdown selection (under the ``timer_name`` key) come from
    the URL query string, so a shared link restores both the slider position and
    the dropdown choice.
    """
    levels, selected = resolve_level(level)
    options, value = callbacks.dropdown_for_level(selected, "timer_id", kwargs.get("timer_name"))
    return html.Div(
        children=[
            dcc.Location(id=IDS.url, refresh=False),
            html.H2("Timers Dashboard"),
            level_slider(IDS.slider, levels, selected),
            select_dropdown(IDS.dropdown, options, value, "Select a timer"),
            option_tabs(IDS.metrics, METRICS),
            graphs_container(IDS.graphs),
        ]
    )


@callback(
    Output(IDS.url, "search"),
    Input(IDS.slider, "value"),
    Input(IDS.dropdown, "value"),
    prevent_initial_call=True,
)
def update_url_query(level, selection):
    return callbacks.update_url_query(level, selection, "timer_name")


@callback(
    Output(IDS.dropdown, "options"),
    Output(IDS.dropdown, "value"),
    Input(IDS.slider, "value"),
    State(IDS.dropdown, "value"),
    prevent_initial_call=True,
)
def update_dropdown(level, current):
    return callbacks.update_dropdown(level, current, "timer_id")


@callback(
    Output(IDS.graphs, "children"),
    Input(IDS.dropdown, "value"),
    Input(IDS.metrics, "value"),
    Input(IDS.slider, "value"),
)
def update_graphs(value, metric, level):
    plots = callbacks.timer_plots(value, level, "timer_id", "test_name")
    return callbacks.update_graphs(plots, metric, hover_data=["n_calls"], heading_style=callbacks.NESTED_STYLE)


dash.register_page(__name__, path="/timers", name="Timers", layout=layout)
