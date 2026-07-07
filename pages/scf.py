"""SCF page: filled-area plots of SCF iterations per label across versions, served at /scf."""

import dash
from dash import Input, Output, callback, dcc, html
from packaging.version import Version

import callbacks
from components import graphs_container, page_ids
from data import get_scf_data

dash.register_page(__name__, path="/scf", name="SCF")

IDS = page_ids("scf", "url", "graphs")


def layout(**kwargs):
    # SCF has no interactive controls, so the cards are filled by the callback
    # below (keyed off the Location, which fires on page load) rather than inline.
    return html.Div(
        children=[
            dcc.Location(id=IDS.url, refresh=False),
            html.H2("SCF"),
            graphs_container(IDS.graphs),
        ]
    )


@callback(
    Output(IDS.graphs, "children"),
    Input(IDS.url, "pathname"),
)
def update_graphs(pathname):
    df = get_scf_data()
    if df is None or df.empty:
        return html.P("No SCF data available.")

    # One card per test: its labels stack as a filled area when there is more
    # than one, otherwise a single label reads more clearly as a plain line.
    plots = [
        (test_name, group, group["label"].nunique() > 1, "label")
        for test_name, group in df.sort_values(
            "psi4_version", key=lambda x: x.map(Version)
        ).groupby("test_name")
    ]
    return callbacks.update_graphs(plots, "iterations")
