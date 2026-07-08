"""SCF page: filled-area plots of SCF iterations per label across versions, served at /scf."""

import dash
from dash import MATCH, Input, Output, State, callback, ctx, dcc, html
from dash.exceptions import PreventUpdate
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
    # than one, otherwise a single label reads more clearly as a plain line. Each
    # card also carries a collapsible accelerator breakdown of its accelerator_raw.
    plots, extras = [], []
    for test_name, group in df.sort_values(
        "psi4_version", key=lambda x: x.map(Version)
    ).groupby("test_name"):
        plots.append((test_name, group, group["label"].nunique() > 1, "label"))
        extras.append(callbacks.scf_accelerator_detail(test_name))
    return callbacks.update_graphs(plots, "iterations", extras=extras)


@callback(
    Output({"type": callbacks.SCF_ACCEL_CONTENT, "index": MATCH}, "children"),
    Input({"type": callbacks.SCF_ACCEL_TRIGGER, "index": MATCH}, "n_clicks"),
    State({"type": callbacks.SCF_ACCEL_CONTENT, "index": MATCH}, "children"),
    prevent_initial_call=True,
)
def load_accelerator_plot(n_clicks, existing):
    # Build the accelerator plot the first time a card's disclosure is opened,
    # then keep it: native <details> just shows/hides the already-built chart on
    # later toggles, so skip rebuilding when the container already holds one.
    if not n_clicks or existing:
        raise PreventUpdate
    return callbacks.scf_accelerator_content(ctx.triggered_id["index"])
