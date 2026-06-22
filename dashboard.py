"""Create and run a multi-page Dash app on a specified server address.

Usage:
    python dashboard.py --address 127.0.0.1:8050
"""

import argparse

import dash
from dash import Dash, dcc, html

from data import get_dataframe, set_dataframe, load_scf_iterations, set_scf_accels, set_scf_labels


def parse_address(address):
    """Split an "host:port" string into (host, port)."""
    host, _, port = address.partition(":")
    return host or None, int(port) if port else None


def create_app():
    """Build the multi-page Dash app from the .csv files found in the given path."""
    set_dataframe(get_dataframe())
    df = load_scf_iterations()
    set_scf_labels(df)
    set_scf_accels(df)

    app = Dash(__name__, use_pages=True, suppress_callback_exceptions=True)
    app.layout = html.Div(
        children=[
            html.Header(
                className="site-header",
                children=html.Div(
                    className="header-inner",
                    children=[
                        html.H1(
                            className="site-brand",
                            children=[
                                "Psi",
                                html.Span("4", className="brand-accent"),
                                " Dashboard",
                            ],
                        ),
                        html.Nav(
                            className="site-nav",
                            children=[
                                dcc.Link(page["name"], href=page["relative_path"], refresh=True)
                                for page in dash.page_registry.values()
                            ],
                        ),
                    ],
                ),
            ),
            html.Main(className="page-content", children=dash.page_container),
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
