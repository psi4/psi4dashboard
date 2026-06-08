"""Create and run a Dash app on a specified server address.

Usage:
    python dashboard.py --path /path/to/data --address 127.0.0.1:8050
"""

import argparse
import glob
import os

import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, callback, dcc, html


def parse_address(address):
    """Split an "host:port" string into (host, port)."""
    host, _, port = address.partition(":")
    return host or None, int(port) if port else None


def create_app(path):
    """Build the Dash app, listing the .csv files found in the given path."""
    csv_files = sorted(
        os.path.relpath(f, path)
        for f in glob.glob(os.path.join(path, "**", "*.csv"), recursive=True)
    )

    # Read each CSV into a DataFrame, keyed by its parent directory name.
    dataframes = {
        os.path.basename(os.path.dirname(name)): pd.read_csv(os.path.join(path, name))
        for name in csv_files
    }
    
    app = Dash(__name__)
    app.layout = html.Div(
        children=[
            html.H1("Psi4 Dashboard"),
            html.H2("CSV files"),
            dcc.Dropdown(
                id="dataframe-dropdown",
                options=[name for name in dataframes.keys()],
                value=next(iter(dataframes), None),
                placeholder="Select a dataframe",
            ),
            dcc.Graph(id="dataframe-graph"),
        ]
    )

    @callback(
        Output("dataframe-graph", "figure"),
        Input("dataframe-dropdown", "value"),
    )
    def update_graph(name):
        df = dataframes.get(name)
        if df is None:
            return px.bar()
        fig = px.bar(
            df,
            y="timer_name",
            x=["wall_time", "user_time", "system_time"],
            orientation="h",
            barmode="stack",
            hover_data=["n_calls"],
        )
        # Show shortened y-axis labels; the full name remains visible on hover.
        def shorten(label, limit=25):
            return label if len(label) <= limit else label[: limit - 1] + "…"

        fig.update_yaxes(
            tickmode="array",
            tickvals=df["timer_name"],
            ticktext=[shorten(name) for name in df["timer_name"]],
        )
        # Scale height with the number of bars so they stay readable.
        fig.update_layout(height=max(400, 25 * len(df)))
        return fig

    return app


def main():
    parser = argparse.ArgumentParser(description="Run a Dash app on a server.")
    parser.add_argument(
        "-p", "--path", default=os.getcwd(), help="Path the app should use."
    )
    parser.add_argument(
        "-a",
        "--address",
        default="",
        help='Server address as "host:port" (e.g. 127.0.0.1:8050).',
    )
    args = parser.parse_args()

    host, port = parse_address(args.address)
    app = create_app(args.path)

    run_kwargs = {}
    if host:
        run_kwargs["host"] = host
    if port:
        run_kwargs["port"] = port
    app.run(**run_kwargs)


if __name__ == "__main__":
    main()
