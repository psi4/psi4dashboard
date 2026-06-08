"""Create and run a Dash app on a specified server address.

Usage:
    python dashboard.py --path /path/to/data --address 127.0.0.1:8050
"""

import argparse
import glob
import os
import random

import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, callback, dcc, html


def parse_address(address):
    """Split an "host:port" string into (host, port)."""
    host, _, port = address.partition(":")
    return host or None, int(port) if port else None

def get_dataframe(path):
    """Read every .csv under path into a single DataFrame.

    Each CSV gets a "test_name" column set to the name of its parent
    directory, and all the frames are concatenated together.
    """
    csv_files = sorted(
        os.path.relpath(f, path)
        for f in glob.glob(os.path.join(path, "**", "*.csv"), recursive=True)
    )

    columns = ["wall_time", "user_time", "system_time"]

    # Read every CSV first, before applying any jitter.
    base_frames = []
    for name in csv_files:
        df = pd.read_csv(os.path.join(path, name))
        df["test_name"] = os.path.basename(os.path.dirname(name))
        base_frames.append(df)

    # Combined total across all frames, used to weight the shared jitter.
    grand_total = sum(df[columns].to_numpy().sum() for df in base_frames)

    versions = []
    for version in range(1, 6):
        # A different random jitter per version, shared across all frames.
        jitter = random.uniform(-0.05, 0.05) * grand_total

        for base in base_frames:
            df = base.copy()
            df["version"] = version

            # This frame's cumulative total, and its share of the jitter.
            total = df[columns].to_numpy().sum()
            frame_jitter = jitter * (total / grand_total)

            # Each row's sum and its proportional slice of this frame's jitter.
            row_sum = df[columns].sum(axis=1)
            row_jitter = frame_jitter * (row_sum / total)

            # Split each row's jitter across its columns by each entry's weight.
            for col in columns:
                entry_weight = df[col] / row_sum
                df[col] += row_jitter * entry_weight

            versions.append(df)

    return pd.concat(versions, ignore_index=True)


def create_app(path):
    """Build the Dash app, listing the .csv files found in the given path."""
    dataframe = get_dataframe(path)
    test_names = sorted(dataframe["test_name"].unique())

    app = Dash(__name__)
    app.layout = html.Div(
        children=[
            html.H1("Psi4 Dashboard"),
            html.H2("CSV files"),
            dcc.Dropdown(
                id="dataframe-dropdown",
                options=test_names,
                value=test_names[0] if test_names else None,
                placeholder="Select a dataframe",
            ),
            html.Div(
                id="dataframe-graphs",
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(400px, 1fr))",
                    "gap": "1rem",
                },
            ),
        ]
    )

    @callback(
        Output("dataframe-graphs", "children"),
        Input("dataframe-dropdown", "value"),
    )
    def update_graphs(name):
        df = dataframe[dataframe["test_name"] == name]
        if df.empty:
            return []

        # One graph per timer, showing how its times change across versions.
        graphs = []
        for timer_name, group in df.groupby("timer_name"):
            group = group.sort_values("version")
            fig = px.line(
                group,
                x="version",
                y=["wall_time", "user_time", "system_time"],
                markers=True,
                title=timer_name,
                hover_data=["n_calls"],
            )
            # Show every version as a discrete tick on the x-axis.
            fig.update_xaxes(tickmode="linear", dtick=1)
            # Keep each graph short so more fit on screen at once.
            fig.update_layout(height=250, margin=dict(t=40, b=30))
            graphs.append(dcc.Graph(figure=fig))
        return graphs

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
