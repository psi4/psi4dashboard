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

from data import (
    get_groups,
    get_parallelism_children,
    get_parallelism_slice,
    get_parallelism_tests,
    get_scf_accelerators,
    get_scf_data,
    get_timing_children,
    get_timing_options,
    get_timing_slice,
)
from theme import ACCELERATOR_COLORS, style_figure

# Timer ids encode their hierarchy as ``parent;child;grandchild``. Splitting on
# this separator and indenting each level two tabs deeper renders the nesting.
NESTING_SEP = ";"

# Preserve the newlines and tabs from ``nest_label`` when rendering. tab-size
# keeps each indent compact rather than the 8-space browser default.
NESTED_STYLE = {"whiteSpace": "pre", "tabSize": 2}

# Pattern-matching id ``type``s for an SCF card's lazy accelerator breakdown: the
# summary the user clicks (trigger) and the container its plot is built into
# (content). Both carry the test_name as their ``index`` so the page's MATCH
# callback maps a click to the right card.
SCF_ACCEL_TRIGGER = "scf-accel-trigger"
SCF_ACCEL_CONTENT = "scf-accel-content"


def nest_label(text):
    """Render a ``;``-separated timer id as indented, nested lines.

    Each segment after the first starts a new line indented two tabs deeper, so
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
    values = get_timing_options(column, level)
    value = current if current in values else (values[0] if values else None)
    options = [{"label": nest_label(v), "value": v} for v in values]
    return options, value


def card_y_max(df, y, area, x="psi4_version"):
    """Return the tallest y value a card's chart will reach, or 0 when empty.

    For a stacked area chart the visible height at each x position is the sum of
    the series there, so the peak is the largest per-``x`` total; a single line
    just peaks at its own maximum. Used to give every card on a page one shared y
    range.
    """
    if df is None or df.empty or y not in df:
        return 0
    peak = df.groupby(x)[y].sum().max() if area else df[y].max()
    return 0 if peak != peak else peak  # coerce NaN (all-empty) to 0


def graph_group(heading, df, y, x="psi4_version", color=None, area=False, hover_data=None, heading_style=None, y_max=None, extra=None, color_map=None):
    """Build one card: a heading plus an area or line chart of ``df`` over ``x``.

    ``x`` is the x-axis column (versions for the timer pages, cores for the
    parallelism page). ``area`` selects a stacked filled-area chart (a
    multi-series breakdown) rather than a single line; ``y``/``color``/
    ``hover_data`` pick the plotted columns. ``heading_style`` styles the card
    heading (e.g. to preserve the indentation of a nested timer name). ``y_max``
    fixes the top of the y-axis so every card on a page shares one scale; when
    omitted the axis auto-scales. ``extra`` is an optional element appended after
    the graph (e.g. the SCF page's collapsible accelerator breakdown).
    ``color_map`` pins specific ``color`` categories to fixed colors (so the same
    category is painted identically across cards); ``None`` keeps Plotly Express's
    default sequence.
    """
    plot = px.area if area else px.line
    fig = plot(
        df,
        x=x,
        y=y,
        color=color,
        markers=True,
        hover_data=hover_data,
        color_discrete_map=color_map,
    )
    # Show every x value as a discrete tick on the x-axis.
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
        children=[html.H3(heading, style=heading_style), dcc.Graph(figure=fig)] + ([extra] if extra else []),
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


def update_graphs(plots, y, x="psi4_version", hover_data=None, heading_style=None, unify_y=False, extras=None):
    """Build one card per plot spec, optionally sharing a single page-wide y range.

    ``plots`` is a list of ``(heading, df, area, color)`` specs — one per card —
    resolved by the caller (see ``timer_plots`` for the Tests/Timers pages,
    ``parallelism_plots`` for the parallelism page, or the SCF page for its own).
    Column ``y`` is plotted against ``x`` for every card; ``hover_data`` and
    ``heading_style`` apply uniformly. When ``unify_y`` is set the y-axis top is
    fixed to the tallest card's peak so the cards read against a common scale;
    otherwise each card auto-scales to its own data. ``extras`` is an optional
    list parallel to ``plots`` supplying one appended element per card (``None``
    for a card with no extra); when omitted no card gets one.
    """
    y_max = max((card_y_max(df, y, area, x) for _, df, area, _ in plots), default=0) if unify_y else None
    extras = extras or [None] * len(plots)
    return [
        graph_group(
            heading,
            df,
            y,
            x=x,
            color=color,
            area=area,
            hover_data=hover_data,
            heading_style=heading_style,
            y_max=y_max,
            extra=extra,
        )
        for (heading, df, area, color), extra in zip(plots, extras)
    ]


def scf_accelerator_detail(test_name):
    """Collapsible accelerator-breakdown shell for one SCF test (content built lazily).

    An ``html.Details`` whose summary is a pattern-matching trigger and whose body
    is an initially empty, loading-wrapped container. The SCF page's ``MATCH``
    callback fills that container from ``scf_accelerator_content`` the first time
    the disclosure is opened, so no plot is built until a user expands the card.
    Every loaded SCF test has accelerator data (``create_scf_df`` requires it), so
    a shell is always emitted. Pass the result as an ``extra`` for the test's card.
    """
    return html.Details(children=[
        html.Summary(
            "View accelerator breakdown",
            id={"type": SCF_ACCEL_TRIGGER, "index": test_name},
            n_clicks=0,
        ),
        dcc.Loading(
            html.Div(id={"type": SCF_ACCEL_CONTENT, "index": test_name}),
            type="circle",
            color="#5f99cf",
        ),
    ])


def scf_accelerator_content(test_name):
    """Build the accelerator-breakdown ``graph_group`` for one SCF test, on demand.

    Called by the SCF page's lazy callback when a card's disclosure is first
    opened. Stacked-area chart of ``accelerator_raw`` (iterations vs psi4_version,
    colored by accelerator; a single line when there is one accelerator), or a
    short message when the test has no accelerator data.
    """
    df = get_scf_accelerators(test_name)
    if df is None or df.empty:
        return html.P("No accelerator data.")
    area = df["accelerator"].nunique() > 1
    return graph_group("Accelerator breakdown", df, "iterations", color="accelerator", area=area,
                       color_map=ACCELERATOR_COLORS)


def timer_plots(value, level, select_column, group_column):
    """Resolve the ``(heading, df, area, color)`` card specs for a timer/test page.

    One spec per ``group_column`` value for the current selection: a timer with
    children yields a filled-area breakdown of those children (colored by child
    timer_name); a leaf timer yields a single line. Headings are the nested,
    indented timer names. Feed the result to ``update_graphs``.
    """
    df = get_timing_slice(level=level, column=select_column, value=value)
    plots = []
    for key, group in get_groups(df, group_column):
        timer_id = group["timer_id"].iloc[0]
        test_name = group["test_name"].iloc[0]
        children = get_timing_children(timer_id, test_name)
        has_children = children is not None and not children.empty
        plots.append((
            nest_label(key),
            children if has_children else group,
            has_children,
            "timer_name" if has_children else None,
        ))
    return plots


def parallelism_plots(test_name, version, level):
    """Resolve the ``(heading, df, area, color)`` card specs for the parallelism page.

    One spec per ``timer_id`` at ``level`` for the selected test and version,
    plotted against cores: a timer with children yields a filled-area breakdown
    of those children (colored by child timer_name); a leaf timer yields a single
    line. Headings are the nested, indented timer names. Feed to ``update_graphs``
    with ``x="cores"``.
    """
    df = get_parallelism_slice(level=level, test_name=test_name, version=version)
    plots = []
    for key, group in get_groups(df, "timer_id"):
        timer_id = group["timer_id"].iloc[0]
        children = get_parallelism_children(timer_id, test_name, version)
        has_children = children is not None and not children.empty
        plots.append((
            nest_label(key),
            children if has_children else group,
            has_children,
            "timer_name" if has_children else None,
        ))
    return plots


def parallelism_tests(version, current=None):
    """Return ``(options, value)`` for the test dropdown, limited to ``version``.

    The current selection is preserved when it still has data in the chosen
    version, otherwise it falls back to the first test (or ``None`` when empty).
    """
    tests = get_parallelism_tests(version)
    value = current if current in tests else (tests[0] if tests else None)
    options = [{"label": t, "value": t} for t in tests]
    return options, value


def parallelism_url_query(level, version, test):
    """Reflect the slider level, version, and test selection into the URL query."""
    params = {"level": level}
    if version is not None:
        params["version"] = version
    if test is not None:
        params["test_name"] = test
    return "?" + urlencode(params)
