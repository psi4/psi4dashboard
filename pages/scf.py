"""SCF page: filled-area plots of SCF iterations per label across versions, served at /scf."""

import dash
import plotly.express as px
from dash import dcc, html
from packaging.version import Version

from data import get_scf_data
from theme import style_figure

dash.register_page(__name__, path="/scf", name="SCF")


def _area_group(test_name, group):
    """Build one card: a heading plus a chart for a single test.

    With more than one label, iterations are stacked by label as a filled-area
    chart so each label's contribution reads against a common baseline. With a
    single label there is nothing to stack, so a plain line chart is clearer.
    """
    if group["label"].nunique() > 1:
        fig = px.area(group, x="psi4_version", y="iterations", color="label", markers=True)
    else:
        fig = px.line(group, x="psi4_version", y="iterations", color="label", markers=True)
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
    df = get_scf_data()
    if df is None or df.empty:
        return html.Div(children=[html.H2("SCF"), html.P("No SCF data available.")])

    return html.Div(
        children=[
            html.H2("SCF"),
            *[
                _area_group(test_name, group)
                for test_name, group in df.sort_values("psi4_version", key=lambda x: x.map(Version)).groupby("test_name")
            ],
        ]
    )
