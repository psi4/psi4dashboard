"""SCF page: filled-area plots of SCF iterations per label across versions, served at /scf."""

import dash
import plotly.express as px
from dash import dcc, html

from data import get_scf_labels
from theme import style_figure

dash.register_page(__name__, path="/scf", name="SCF")


def _area_group(test_name, group):
    """Build one card: a heading plus a filled-area chart for a single test.

    Iterations are stacked by label across versions so each label's
    contribution reads against a common baseline.
    """
    fig = px.area(
        group,
        x="version",
        y="iterations",
        color="label",
        markers=True,
    )
    # Show every version as a discrete tick on the x-axis.
    fig.update_xaxes(tickmode="linear", dtick=1)
    # Anchor the y-axis at 0 so areas read against a common baseline.
    fig.update_yaxes(rangemode="tozero")
    # Keep each graph short so more fit on screen at once.
    fig.update_layout(height=250, margin=dict(l=40, r=10, t=10, b=30))
    style_figure(fig)
    return html.Div(
        className="graph-group",
        children=[html.H3(test_name), dcc.Graph(figure=fig)],
    )


def layout(**kwargs):
    df = get_scf_labels()
    if df is None or df.empty:
        return html.Div(children=[html.H2("SCF"), html.P("No SCF data available.")])

    return html.Div(
        children=[
            html.H2("SCF"),
            *[
                _area_group(test_name, group)
                for test_name, group in df.sort_values("version").groupby("test_name")
            ],
        ]
    )
