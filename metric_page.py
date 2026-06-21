"""Shared builder for the metric line-chart pages (Tests and Timers).

Both pages render the same scaffold — a level slider, a dropdown, a metric
checklist, and a grid of per-version line charts — and differ only in which
column the dropdown selects and which column the charts are grouped by.
``build_metric_page`` registers one such page so the layout, callbacks, and
chart styling live in a single place and common changes are made once.
"""

from urllib.parse import urlencode

import plotly.express as px
from dash import Input, Output, State, callback, dcc, html

from data import get_groups, get_levels, get_options
from theme import style_figure

METRICS = ["wall_time", "user_time", "system_time"]

# Grid layout for the per-metric graphs.
# ``alignItems: start`` keeps cells from stretching to the row height, which
# otherwise feeds the responsive Plotly graphs a growing height and makes them
# expand vertically without bound.
GRID_STYLE = {
    "display": "grid",
    "gridTemplateColumns": "repeat(auto-fit, minmax(400px, 1fr))",
    "gap": "1rem",
    "alignItems": "start",
}


def _dropdown_for_level(level, column, current=None):
    """Return ``(options, value)`` for the dropdown at the given slider level.

    Options are the distinct values of ``column`` that have data at exactly
    ``level`` (queried from the data layer). The current selection is preserved
    when it is still valid, otherwise it falls back to the first option (or
    ``None`` when empty).
    """
    options = get_options(column, level)
    value = current if current in options else (options[0] if options else None)
    return options, value


def _graph_group(label, group, metrics):
    """Build one card: a heading plus a line chart per selected metric."""
    figures = []
    
    for metric in metrics:
        fig = px.line(
            group,
            x="version",
            y=metric,
            color='timer_name',
            markers=True,
            hover_data=["n_calls"],
        )
        # Show every version as a discrete tick on the x-axis.
        fig.update_xaxes(tickmode="linear", dtick=1)
        # Keep each graph short so more fit on screen at once.
        fig.update_layout(height=250, margin=dict(l=40, r=10, t=10, b=30))
        style_figure(fig)
        figures.append(dcc.Graph(figure=fig))
    return html.Div(
        className="graph-group",
        children=[
            html.H3(label),
            html.Div(figures, style=GRID_STYLE),
        ],
    )


def build_metric_page(
    id_prefix,
    title,
    placeholder,
    select_column,
    group_column,
    query_param,
):
    """Build a metric line-chart page's layout and register its callbacks.

    ``select_column`` is the column the dropdown picks a value from;
    ``group_column`` is the column the charts are grouped by (one card each);
    ``query_param`` is the URL query-string key the dropdown selection is
    stored under (e.g. ``test_name``), letting a shared link restore it.
    All other behaviour is identical across pages so it lives here.

    Returns the ``layout`` callable; the caller passes it to
    ``dash.register_page`` so the per-page route stays in the page module
    (which is also where Dash's page scanner looks for ``register_page``).
    """
    url_id = f"{id_prefix}-url"
    slider_id = f"{id_prefix}-slider"
    dropdown_id = f"{id_prefix}-dropdown"
    metrics_id = f"{id_prefix}-metrics"
    graphs_id = f"{id_prefix}-graphs"

    def layout(level=None, **kwargs):
        """Build the page layout from the data loaded at startup.

        ``level`` and the dropdown selection (under the ``query_param`` key)
        come from the URL query string, so a shared link restores both the
        slider position and the dropdown choice.
        """
        levels = get_levels()
        level_min = int(levels[0]) if levels else 0
        level_max = int(levels[-1]) if levels else 0

        # Seed the slider from the URL when present, otherwise start at the
        # minimum (top of the hierarchy).
        selected = int(level) if level is not None else level_min
        # Seed the dropdown from the URL too, keeping it only if still valid.
        options, value = _dropdown_for_level(
            selected, select_column, kwargs.get(query_param)
        )

        return html.Div(
            children=[
                dcc.Location(id=url_id, refresh=False),
                html.H2(title),
                dcc.Slider(
                    id=slider_id,
                    min=level_min,
                    max=level_max,
                    step=1,
                    value=selected,
                    marks={int(v): str(int(v)) for v in levels},
                    allow_direct_input=False,
                ),
                dcc.Dropdown(
                    id=dropdown_id,
                    options=options,
                    value=value,
                    placeholder=placeholder,
                    style={"marginTop": "1.5rem"},
                ),
                dcc.Checklist(
                    id=metrics_id,
                    options=METRICS,
                    value=METRICS,
                    inline=True,
                    style={"margin": "0.5rem 0"},
                ),
                html.Div(id=graphs_id),
            ]
        )

    @callback(
        Output(url_id, "search"),
        Input(slider_id, "value"),
        Input(dropdown_id, "value"),
        prevent_initial_call=True,
    )
    def update_url_query(level, selection):
        """Reflect the slider level and dropdown selection into the URL."""
        params = {"level": level}
        if selection is not None:
            params[query_param] = selection
        return "?" + urlencode(params)

    @callback(
        Output(dropdown_id, "options"),
        Output(dropdown_id, "value"),
        Input(slider_id, "value"),
        State(dropdown_id, "value"),
        prevent_initial_call=True,
    )
    def update_dropdown(level, current):
        """Limit the dropdown to values that have data at the given level.

        Skipped on initial load (the layout already seeds the dropdown) so that
        opening a page does not cascade into a URL rewrite.
        """
        return _dropdown_for_level(level, select_column, current)

    @callback(
        Output(graphs_id, "children"),
        Input(dropdown_id, "value"),
        Input(metrics_id, "value"),
        Input(slider_id, "value"),
    )
    def update_graphs(value, metrics, level):
        # One card per group_column value, with rows filtered and sorted by the
        # data layer so the line follows versions.
        return [
            _graph_group(key, group, metrics)
            for key, group in get_groups(select_column, value, level, group_column)
        ]

    return layout
