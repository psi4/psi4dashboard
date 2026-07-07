"""Callback logic and chart helpers for the metric line-chart pages.

These are plain functions with no Dash wiring — the Tests and Timers pages
register the actual ``@callback``s against their own element ids and delegate
here, passing the columns and query-string key that differ between the two
pages.
"""

from urllib.parse import urlencode

import plotly.express as px
from dash import dcc, html
from packaging.version import Version

from data import get_children, get_groups, get_options, get_scf_data, get_timing_data
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


def card_y_max(df, y, area):
    """Return the tallest y value a card's chart will reach, or 0 when empty.

    For a stacked area chart the visible height at each version is the sum of the
    series there, so the peak is the largest per-version total; a single line just
    peaks at its own maximum. Used to give every card on a page one shared y range.
    """
    if df is None or df.empty or y not in df:
        return 0
    peak = df.groupby("psi4_version")[y].sum().max() if area else df[y].max()
    return 0 if peak != peak else peak  # coerce NaN (all-empty) to 0


def graph_group(heading, df, y, color=None, area=False, hover_data=None, heading_style=None, y_max=None):
    """Build one card: a heading plus an area or line chart of ``df`` over versions.

    ``area`` selects a stacked filled-area chart (a multi-series breakdown)
    rather than a single line; ``y``/``color``/``hover_data`` pick the plotted
    columns. ``heading_style`` styles the card heading (e.g. to preserve the
    indentation of a nested timer name). ``y_max`` fixes the top of the y-axis so
    every card on a page shares one scale; when omitted the axis auto-scales.
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
    if y_max and y_max > 0:
        # Pin the top to the page-wide max (with a little headroom so the peak
        # marker isn't clipped) so cards are read against a common scale.
        fig.update_yaxes(range=[0, y_max * 1.05])
    else:
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


def update_graphs(plots, y, hover_data=None, heading_style=None, unify_y=False):
    """Build one card per plot spec, optionally sharing a single page-wide y range.

    ``plots`` is a list of ``(heading, df, area, color)`` specs — one per card —
    resolved by the caller (see ``timer_plots`` for the Tests/Timers pages, or the
    SCF page for its own). Column ``y`` is plotted for every card; ``hover_data``
    and ``heading_style`` apply uniformly. When ``unify_y`` is set the y-axis top
    is fixed to the tallest card's peak so the cards read against a common scale;
    otherwise each card auto-scales to its own data.
    """
    y_max = max((card_y_max(df, y, area) for _, df, area, _ in plots), default=0) if unify_y else None
    return [
        graph_group(
            heading,
            df,
            y,
            color=color,
            area=area,
            hover_data=hover_data,
            heading_style=heading_style,
            y_max=y_max,
        )
        for heading, df, area, color in plots
    ]


def timer_plots(value, level, select_column, group_column):
    """Resolve the ``(heading, df, area, color)`` card specs for a timer/test page.

    One spec per ``group_column`` value for the current selection: a timer with
    children yields a filled-area breakdown of those children (colored by child
    timer_name); a leaf timer yields a single line. Headings are the nested,
    indented timer names. Feed the result to ``update_graphs``.
    """
    df = get_timing_data(level=level, column=select_column, value=value)
    plots = []
    for key, group in get_groups(df, group_column):
        timer_id = group["timer_id"].iloc[0]
        test_name = group["test_name"].iloc[0]
        children = get_children(timer_id, test_name)
        has_children = children is not None and not children.empty
        plots.append((
            nest_label(key),
            children if has_children else group,
            has_children,
            "timer_name" if has_children else None,
        ))
    return plots
