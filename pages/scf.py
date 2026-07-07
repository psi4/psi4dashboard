"""SCF page: filled-area plots of SCF iterations per label across versions, served at /scf."""

import dash
from dash import html
from packaging.version import Version

from callbacks import graph_group
from components import graphs_container
from data import get_scf_data

dash.register_page(__name__, path="/scf", name="SCF")


def layout(**kwargs):
    df = get_scf_data()
    if df is None or df.empty:
        return html.Div(children=[html.H2("SCF"), html.P("No SCF data available.")])

    # SCF has no interactive controls, so the cards are built here and rendered
    # straight into the shared graphs container rather than filled by a callback.
    # With more than one label the iterations stack as a filled area; a single
    # label has nothing to stack, so a plain line reads more clearly.
    cards = [
        graph_group(
            test_name,
            group,
            "iterations",
            color="label",
            area=group["label"].nunique() > 1,
        )
        for test_name, group in df.sort_values(
            "psi4_version", key=lambda x: x.map(Version)
        ).groupby("test_name")
    ]
    return html.Div(
        children=[
            html.H2("SCF"),
            graphs_container("scf-graphs", cards),
        ]
    )
