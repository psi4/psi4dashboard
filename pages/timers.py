"""Timers page: line charts of a selected timer's metrics across tests, served at /timers."""

from urllib.parse import urlencode

import dash
import plotly.express as px
from dash import Input, Output, callback, dcc, html

from data import get_data

dash.register_page(__name__, path="/timers", name="Timers")

METRICS = ["wall_time", "user_time", "system_time"]

# Grid layout for the per-metric graphs.
GRID_STYLE = {
    "display": "grid",
    "gridTemplateColumns": "repeat(auto-fit, minmax(400px, 1fr))",
    "gap": "1rem",
}


def layout(level=None, **kwargs):
    """Build the page layout from the DataFrame loaded at startup.

    ``level`` comes from the URL query string, so a shared link restores the
    slider's selection.
    """
    dataframe = get_data()

    levels = sorted(dataframe["level"].unique()) if dataframe is not None else []
    level_min = int(levels[0]) if levels else 0
    level_max = int(levels[-1]) if levels else 0

    # Seed the slider from the URL when present, otherwise default to the minimum.
    value = int(level) if level is not None else level_min

    return html.Div(
        children=[
            dcc.Location(id="timer-url", refresh=False),
            html.H2("Parent Timers"),
            dcc.Slider(
                id="level-slider",
                min=level_min,
                max=level_max,
                step=1,
                value=value,
                marks={int(v): str(int(v)) for v in levels},
            ),
            dcc.Dropdown(
                id="timer-dropdown",
                placeholder="Select a timer group",
                style={"marginTop": "1.5rem"},
            ),
            dcc.Checklist(
                id="timer-metric-checklist",
                options=METRICS,
                value=METRICS,
                inline=True,
                style={"margin": "0.5rem 0"},
            ),
            html.Div(id="timer-graphs"),
        ]
    )


@callback(
    Output("timer-url", "search"),
    Input("level-slider", "value"),
    prevent_initial_call=True,
)
def update_level_query(level):
    """Reflect the selected level into the URL query string."""
    return "?" + urlencode({"level": level})


@callback(
    Output("timer-dropdown", "options"),
    Output("timer-dropdown", "value"),
    Input("level-slider", "value"),
)
def update_dropdown(level):
    """Populate the timer dropdown with only the timer_ids at the given level."""
    dataframe = get_data()
    if dataframe is None:
        return [], None

    timers = sorted(dataframe[dataframe["level"] == level]["timer_id"].unique())
    return timers, (timers[0] if timers else None)


@callback(
    Output("timer-graphs", "children"),
    Input("timer-dropdown", "value"),
    Input("timer-metric-checklist", "value"),
)
def update_graphs(timer_name, metrics):
    dataframe = get_data()
    if dataframe is None:
        return []

    df = dataframe[(dataframe["timer_id"] == timer_name)]
    if df.empty:
        return []

    # One div per test_name with a single heading and a graph per selected metric.
    df = df.sort_values("version")
    group_divs = []
    for test_name, group in df.groupby("test_name"):
        figures = []
        for metric in metrics:
            fig = px.line(
                group,
                x="version",
                y=metric,
                markers=True,
                hover_data=["n_calls"],
            )
            # Show every version as a discrete tick on the x-axis.
            fig.update_xaxes(tickmode="linear", dtick=1)
            # Keep each graph short so more fit on screen at once.
            fig.update_layout(height=250, margin=dict(l=40, r=10, t=10, b=30))
            figures.append(dcc.Graph(figure=fig))
        group_divs.append(
            html.Div(
                children=[
                    html.H3(test_name, style={"margin": "0 0 0.25rem 0"}),
                    html.Div(figures, style=GRID_STYLE),
                ],
                style={"marginBottom": "1.5rem"},
            )
        )
    return group_divs
