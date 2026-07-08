"""Home landing page, served at /."""

import dash
from dash import dcc, html

dash.register_page(__name__, path="/", name="Home")


def layout(**kwargs):
    return html.Div(
        children=[
            html.H2("Welcome"),
            html.P("Explore Psi4 timing data across versions."),
            dcc.Link("View tests →", href="/tests", className="btn-link"),
        ]
    )
