"""Shared Plotly styling so charts match the psicode.org-inspired dark theme."""

# Palette mirrors assets/style.css.
BG_CARD = "#292f36"
TEXT_HEADING = "#afbac4"
TEXT_BODY = "#8f98a1"
GRID = "#4e595f"

# Muted diagonal for the ideal-speedup (y=x) reference line: visible but
# subordinate to the data lines it's compared against.
REF_LINE = TEXT_BODY

# Accent colors used to cycle the per-metric/per-trace lines.
COLORWAY = ["#5f99cf", "#6cb670", "#2c9091", "#44689d", "#c79a4b", "#b06a8e"]

# Fixed accelerator-label -> green mapping so every SCF accelerator graph paints a
# given scheme the same shade (color follows the label, not its stacking order).
# A single-hue green ramp (dark->light), so the accelerator plot reads as its own
# green family.
ACCELERATOR_COLORS = {
    "DIIS": "#31763a",
    "ADIIS/DIIS": "#438c4b",
    "ADIIS": "#64b26b",
    "SOSCF": "#98d19c",
    "NONE": "#d0ead0",
}


def style_figure(fig):
    """Apply the dashboard's dark theme to a Plotly figure in place."""
    fig.update_layout(
        paper_bgcolor=BG_CARD,
        plot_bgcolor=BG_CARD,
        font=dict(family="Raleway, sans-serif", color=TEXT_BODY),
        colorway=COLORWAY,
        title_font=dict(family="Dosis, sans-serif", color=TEXT_HEADING),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID)
    return fig
