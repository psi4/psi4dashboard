"""Callback logic and chart helpers for the metric line-chart pages.

These are plain functions with no Dash wiring — the Tests and Timers pages
register the actual ``@callback``s against their own element ids and delegate
here, passing the columns and query-string key that differ between the two
pages.
"""

from urllib.parse import urlencode

import plotly.express as px
from dash import dcc, html

from data import get_children, get_groups, get_options
from theme import style_figure

# Timer ids encode their hierarchy as ``parent;child;grandchild``. Splitting on
# this separator and indenting each level one tab deeper renders the nesting.
NESTING_SEP = ";"

# Preserve the newlines and tabs from ``nest_label`` when rendering. tab-size
# keeps each indent compact rather than the 8-space browser default.
NESTED_STYLE = {"whiteSpace": "pre", "tabSize": 2}


def nest_label(text):
    """Render a ``;``-separated timer id as indented, nested lines.

    Each segment after the first starts a new line indented one tab deeper, so
    the timer's place in the hierarchy reads at a glance. Must be paired with
    ``NESTED_STYLE`` (or equivalent CSS) so the whitespace is not collapsed.
    """
    parts = text.split(NESTING_SEP)
    return "\n".join("\t" * 2 * depth + part for depth, part in enumerate(parts))


def dropdown_for_level(level, column, current=None):
    """Return ``(options, value)`` for the dropdown at the given slider level.

    Options are the distinct values of ``column`` that have data at exactly
    ``level`` (queried from the data layer), each labelled as a nested,
    indented timer name while keeping the raw value. The current selection is
    preserved when it is still valid, otherwise it falls back to the first
    option (or ``None`` when empty).
    """
    values = get_options(column, level)
    value = current if current in values else (values[0] if values else None)
    options = [{"label": nest_label(v), "value": v} for v in values]
    return options, value


def graph_group(heading, df, y, color=None, area=False, hover_data=None, heading_style=None):
    """Build one card: a heading plus an area or line chart of ``df`` over versions.

    ``area`` selects a stacked filled-area chart (a multi-series breakdown)
    rather than a single line; ``y``/``color``/``hover_data`` pick the plotted
    columns. ``heading_style`` styles the card heading (e.g. to preserve the
    indentation of a nested timer name).
    """
    plot = px.area if area else px.line
    fig = plot(
        df,
        x="psi4_version",
        y=y,
        color=color,
        markers=True,
        hover_data=hover_data,
    )
    # Show every version as a discrete tick on the x-axis.
    fig.update_xaxes(tickmode="linear", dtick=1)
    # Anchor the y-axis at 0 so areas/lines are read against a common baseline.
    fig.update_yaxes(rangemode="tozero")
    # Keep each graph short so more fit on screen at once.
    fig.update_layout(height=250, margin=dict(l=40, r=10, t=10, b=30))
    style_figure(fig)
    return html.Div(
        className="graph-group",
        children=[html.H3(heading, style=heading_style), dcc.Graph(figure=fig)],
    )


def update_url_query(level, selection, query_param):
    """Reflect the slider level and dropdown selection into the URL query string."""
    params = {"level": level}
    if selection is not None:
        params[query_param] = selection
    return "?" + urlencode(params)


def update_dropdown(level, current, select_column):
    """Return the dropdown options/value limited to data at ``level``.

    The registering callback uses ``prevent_initial_call`` (the layout already
    seeds the dropdown), so this only runs when the slider actually changes and
    opening a page does not cascade into a URL rewrite.
    """
    return dropdown_for_level(level, select_column, current)


def update_graphs(value, metric, level, select_column, group_column):
    """Return one graph card per ``group_column`` value for the current selection.

    A card whose timer has children shows a filled-area breakdown of those
    children (colored by child timer_name); a leaf timer shows a single line.
    Rows are filtered and sorted by the data layer so each line follows versions.
    """
    cards = []
    for key, group in get_groups(select_column, value, level, group_column):
        timer_id = group["timer_id"].iloc[0]
        test_name = group["test_name"].iloc[0]
        children = get_children(timer_id, test_name)
        has_children = children is not None and not children.empty
        cards.append(
            graph_group(
                nest_label(key),
                children if has_children else group,
                metric,
                color="timer_name" if has_children else None,
                area=has_children,
                hover_data=["n_calls"],
                heading_style=NESTED_STYLE,
            )
        )
    return cards
