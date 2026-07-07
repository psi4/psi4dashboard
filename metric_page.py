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

from data import get_children, get_groups, get_levels, get_options
from theme import GRID, style_figure

METRICS = ["wall_time", "user_time", "system_time"]

# Timer ids encode their hierarchy as ``parent§child§grandchild``. Splitting on
# this separator and indenting each level one tab deeper renders the nesting.
NESTING_SEP = "§"

# Preserve the newlines and tabs from ``_nest_label`` when rendering. tab-size
# keeps each indent compact rather than the 8-space browser default.
NESTED_STYLE = {"whiteSpace": "pre", "tabSize": 2}


def _nest_label(text):
    """Render a ``§``-separated timer id as indented, nested lines.

    Each segment after the first starts a new line indented one tab deeper, so
    the timer's place in the hierarchy reads at a glance. Must be paired with
    ``NESTED_STYLE`` (or equivalent CSS) so the whitespace is not collapsed.
    """
    parts = text.split(NESTING_SEP)
    return "\n".join("\t" * 2 * depth + part for depth, part in enumerate(parts))


def _dropdown_for_level(level, column, current=None):
    """Return ``(options, value)`` for the dropdown at the given slider level.

    Options are the distinct values of ``column`` that have data at exactly
    ``level`` (queried from the data layer), each labelled as a nested,
    indented timer name while keeping the raw value. The current selection is
    preserved when it is still valid, otherwise it falls back to the first
    option (or ``None`` when empty).
    """
    values = get_options(column, level)
    value = current if current in values else (values[0] if values else None)
    options = [{"label": _nest_label(v), "value": v} for v in values]
    return options, value


def _graph_group(label, group, metric):
    """Build one card: a heading plus the chart for the selected metric.

    If the card's timer has children, show a filled-area breakdown of those
    children (colored by child timer_name); otherwise a single line.
    """
    timer_id = group["timer_id"].iloc[0]
    test_name = group["test_name"].iloc[0]
    children = get_children(timer_id, test_name)
    if children is not None and not children.empty:
        fig = px.area(
            children,
            x="psi4_version",
            y=metric,
            color="timer_name",
            markers=True,
            hover_data=["n_calls"],
        )
    else:
        fig = px.line(
            group,
            x="psi4_version",
            y=metric,
            markers=True,
            hover_data=["n_calls"],
        )
    # Show every version as a discrete tick on the x-axis.
    fig.update_xaxes(tickmode="linear", dtick=1)
    # Anchor the y-axis at 0 so bars/lines are read against a common baseline.
    fig.update_yaxes(rangemode="tozero")
    # Keep each graph short so more fit on screen at once.
    fig.update_layout(height=250, margin=dict(l=40, r=10, t=10, b=30))
    style_figure(fig)
    return html.Div(
        className="graph-group",
        children=[html.H3(_nest_label(label), style=NESTED_STYLE), dcc.Graph(figure=fig)],
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
                    style={"marginTop": "1rem"},
                ),
                dcc.Tabs(
                    id=metrics_id,
                    value=METRICS[0],
                    children=[
                        dcc.Tab(label=m.replace("_", " ").title(), value=m)
                        for m in METRICS
                    ],
                    colors={
                        "border": GRID,
                        "background": "#292f36",
                    },
                    style={"margin": "1rem 0 1rem"},
                ),
                dcc.Loading(
                    children=html.Div(id=graphs_id),
                    type="circle",
                    color="#5f99cf",
                    # The spinner is flex-centered over the full height of the
                    # (tall) graph grid, so on an update it lands in the vertical
                    # middle — off-screen. Align it to the top of the grid, just
                    # under the controls, where it stays visible.
                    style={"alignSelf": "flex-start", "marginTop": "1rem"},
                ),
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
    def update_graphs(value, metric, level):
        # One card per group_column value, with rows filtered and sorted by the
        # data layer so the line follows versions.
        return [
            _graph_group(key, group, metric)
            for key, group in get_groups(select_column, value, level, group_column)
        ]

    return layout
