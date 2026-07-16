"""Dash component builders and layout seeding for the metric line-chart pages.

The Tests and Timers pages render the same scaffold — a level slider, a
dropdown, a metric tab strip, and a grid of per-version line charts. Each
builder here returns one of those pieces so a page assembles its own layout.
``page_ids`` namespaces the element ids any page needs, and ``resolve_level``
seeds the slider identically across the two metric pages.
"""

from collections import namedtuple

from dash import dcc, html

from data import get_timing_levels
from theme import GRID

METRICS = ["wall_time", "user_time", "system_time"]

def page_ids(prefix, *roles):
    """Return a namedtuple of ``prefix``-namespaced ids, one attribute per role.

    e.g. ``page_ids("scf", "url", "graphs").graphs == "scf-graphs"``. A page
    names exactly the roles it renders, so its layout builders and its callbacks
    share the same ids without hand-duplicating the strings.
    """
    return namedtuple("PageIds", roles)(*(f"{prefix}-{role}" for role in roles))


def resolve_level(level, levels=None):
    """Return ``(levels, selected)`` for seeding the slider from the URL.

    ``levels`` is the sorted distinct hierarchy levels; ``selected`` is the
    slider's initial value — ``level`` from the URL when present, otherwise the
    minimum (top of the hierarchy), falling back to 0 when there is no data.
    Pages backed by a different dataset pass their own ``levels``; when omitted
    the timing dataset's levels are used.
    """
    if levels is None:
        levels = get_timing_levels()
    if level is not None:
        selected = int(level)
    else:
        selected = int(levels[0]) if levels else 0
    return levels, selected


def level_slider(slider_id, levels, value):
    """Build the hierarchy-level slider spanning ``levels``, set to ``value``."""
    level_min = int(levels[0]) if levels else 0
    level_max = int(levels[-1]) if levels else 0
    return dcc.Slider(
        id=slider_id,
        min=level_min,
        max=level_max,
        step=1,
        value=value,
        marks={int(v): str(int(v)) for v in levels},
        allow_direct_input=False,
    )


def select_dropdown(dropdown_id, options, value, placeholder, style=None):
    """Build the value-selecting dropdown, seeded with ``options``/``value``."""
    return dcc.Dropdown(
        id=dropdown_id,
        options=options,
        value=value,
        placeholder=placeholder,
        style={"marginTop": "1rem", **(style or {})},
    )


def option_tabs(tabs_id, options, value=None):
    """Build a tab strip choosing one of ``options`` (snake_case strings).

    Tab labels are derived from the option values (``wall_time`` -> "Wall
    Time"). ``value`` selects the initially active tab; it defaults to the
    first option.
    """
    return dcc.Tabs(
        id=tabs_id,
        value=value if value is not None else options[0],
        children=[
            dcc.Tab(label=o.replace("_", " ").title(), value=o)
            for o in options
        ],
        colors={
            "border": GRID,
            "background": "#292f36",
        },
        style={"margin": "1rem 0 1rem"},
    )


def graphs_container(graphs_id, children=None):
    """Build the loading-wrapped container the chart grid renders into.

    Interactive pages leave it empty and populate ``html.Div(id=graphs_id)``
    from a callback; static pages (e.g. SCF) pass their pre-built cards as
    ``children`` to render them directly in the layout.
    """
    return dcc.Loading(
        children=html.Div(id=graphs_id, children=children),
        type="circle",
        color="#5f99cf",
        # Only spin for the whole-grid rebuild (this Div's own children). Without
        # this, dcc.Loading reacts to *any* callback output in its subtree, so a
        # nested per-card callback (e.g. the SCF accelerator toggle) would blank
        # and re-render the entire grid — reading as a full-page reload.
        target_components={graphs_id: "children"},
        # The spinner is flex-centered over the full height of the (tall) graph
        # grid, so on an update it lands in the vertical middle — off-screen.
        # Align it to the top of the grid, just under the controls, where it
        # stays visible.
        style={"alignSelf": "flex-start", "marginTop": "1rem"},
    )
