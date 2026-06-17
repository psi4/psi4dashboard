"""Create and run a multi-page Dash app on a specified server address.

Usage:
    python dashboard.py --path /path/to/data --address 127.0.0.1:8050
"""

import argparse
import os

import dash
from dash import Dash, dcc, html

from data import get_dataframe, set_dataframe


def parse_address(address):
    """Split an "host:port" string into (host, port)."""
    host, _, port = address.partition(":")
    return host or None, int(port) if port else None


def create_app():
    """Build the multi-page Dash app from the .csv files found in the given path."""
    set_dataframe(get_dataframe())

    app = Dash(__name__, use_pages=True, suppress_callback_exceptions=True)
    app.layout = html.Div(
        children=[
            html.Header(
                children=[
                    html.H1("Psi4 Dashboard", style={"margin": 0}),
                    html.Nav(
                        children=[
                            dcc.Link(page["name"], href=page["relative_path"])
                            for page in dash.page_registry.values()
                        ],
                        style={"display": "flex", "gap": "1.5rem"},
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "padding": "1rem 0",
                    "marginBottom": "1rem",
                    "borderBottom": "1px solid #ddd",
                },
            ),
            dash.page_container,
        ]
    )
    return app


def main():
    parser = argparse.ArgumentParser(description="Run a Dash app on a server.")
    parser.add_argument(
        "-a",
        "--address",
        default="",
        help='Server address as "host:port" (e.g. 127.0.0.1:8050).',
    )
    args = parser.parse_args()

    host, port = parse_address(args.address)
    app = create_app()

    run_kwargs = {}
    if host:
        run_kwargs["host"] = host
    if port:
        run_kwargs["port"] = port
    app.run(**run_kwargs, debug=True)


if __name__ == "__main__":
    main()
