"""Tests page: per-test line charts of timer metrics, served at /tests."""

from urllib.parse import urlencode

import dash
import plotly.express as px
from dash import Input, Output, callback, dcc, html

from data import get_data

dash.register_page(__name__, path="/tests", name="Tests")

METRICS = ["wall_time", "user_time", "system_time"]

# Grid layout for the per-metric graphs.
GRID_STYLE = {
    "display": "grid",
    "gridTemplateColumns": "repeat(auto-fit, minmax(400px, 1fr))",
    "gap": "1rem",
}


def layout(min_level=None, max_level=None, **kwargs):
    """Build the page layout from the DataFrame loaded at startup.

    ``min_level``/``max_level`` come from the URL query string, so a shared link
    restores the range slider's selection.
    """
    dataframe = get_data()
    test_names = sorted(dataframe["test_name"].unique()) if dataframe is not None else []

    levels = sorted(dataframe["level"].dropna().unique()) if dataframe is not None else []
    level_min = int(levels[0]) if levels else 0
    level_max = int(levels[-1]) if levels else 0

    # Seed the slider from the URL when present, otherwise span the full range.
    low = int(min_level) if min_level is not None else level_min
    high = int(max_level) if max_level is not None else level_max

    return html.Div(
        children=[
            dcc.Location(id="tests-url", refresh=False),
            html.H2("CSV files"),
            dcc.RangeSlider(
                id="level-rangeslider",
                min=level_min,
                max=level_max,
                step=1,
                value=[low, high],
                marks={int(v): str(int(v)) for v in levels},
            ),
            dcc.Dropdown(
                id="dataframe-dropdown",
                options=test_names,
                value=test_names[0] if test_names else None,
                placeholder="Select a dataframe",
                style={"marginTop": "1.5rem"},
            ),
            dcc.Checklist(
                id="metric-checklist",
                options=METRICS,
                value=METRICS,
                inline=True,
                style={"margin": "0.5rem 0"},
            ),
            html.Div(id="dataframe-graphs"),
        ]
    )


@callback(
    Output("tests-url", "search"),
    Input("level-rangeslider", "value"),
    prevent_initial_call=True,
)
def update_level_query(level_range):
    """Reflect the selected level range into the URL query string."""
    low, high = level_range[0], level_range[1]
    return "?" + urlencode({"min_level": low, "max_level": high})


@callback(
    Output("dataframe-graphs", "children"),
    Input("dataframe-dropdown", "value"),
    Input("metric-checklist", "value"),
    Input("level-rangeslider", "value"),
)
def update_graphs(name, metrics, level_range):
    dataframe = get_data()
    if dataframe is None:
        return []

    low, high = level_range
    df = dataframe[
        (dataframe["test_name"] == name)
        & (dataframe["level"] >= low)
        & (dataframe["level"] <= high)
    ]
    if df.empty:
        return []

    # One div per timer_id with a single heading and a graph per selected metric.
    df = df.sort_values("version")
    group_divs = []
    for timer_id, group in df.groupby("timer_id"):
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
                    html.H3(timer_id, style={"margin": "0 0 0.25rem 0"}),
                    html.Div(figures, style=GRID_STYLE),
                ],
                style={"marginBottom": "1.5rem"},
            )
        )
    return group_divs
