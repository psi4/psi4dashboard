"""Shared data loading and runtime state for the dashboard.

The data path is supplied on the command line at runtime, but Dash imports
page modules when the app is constructed. To bridge that gap, the entry point
loads the DataFrame and stashes it here with ``set_dataframe``; page layouts and
callbacks read filtered slices of it lazily at request time.
"""

import json

import pandas as pd

_dataframe = None


def set_dataframe(df):
    """Store the loaded DataFrame for pages to read later."""
    global _dataframe
    _dataframe = df


def get_data(level=None, column=None, value=None):
    """Return the stored rows narrowed to the requested slice (or None).

    With no arguments the full DataFrame is returned. ``level`` keeps only rows
    at that hierarchy level; ``column`` keeps only rows where that column equals
    ``value`` (so a ``None`` value yields an empty frame). The result is sorted
    by ``version`` so chart lines follow it.
    """
    df = _dataframe
    if df is None:
        return None
    if level is not None:
        df = df[df["level"] == level]
    if column is not None:
        df = df[df[column] == value]
    return df.sort_values("version")


def get_levels():
    """Return the sorted distinct hierarchy levels, for the slider."""
    df = get_data()
    return sorted(df["level"].dropna().unique()) if df is not None else []


def get_options(column, level):
    """Return the sorted distinct values of ``column`` among rows at ``level``.

    Used to populate the dropdown for a given slider level.
    """
    df = get_data(level=level)
    return sorted(df[column].unique()) if df is not None else []


def get_groups(select_column, value, level, group_column):
    """Return chart-ready rows grouped for rendering.

    Rows are filtered to ``select_column == value`` at ``level``, sorted by
    ``version``, and partitioned by ``group_column`` into ``(key, group)`` pairs
    (one per card). Returns an empty list when there is no data or no match.
    """
    df = get_data(level=level, column=select_column, value=value)
    if df is None or df.empty:
        return []
    return list(df.groupby(group_column))


def get_dataframe():
    """Read timers.json file into DataFrame.
    """
    with open("timers.json") as f:
        payload = json.load(f)

        # Each entry in the "timers" array becomes a row, with its keys as columns.
    df = pd.json_normalize(payload["timers"])

    # A timer is "child free" when no other row names it as a parent.
    parent_ids = set(df["parent_id"].dropna())
    df["child_free"] = ~df["timer_id"].isin(parent_ids)

    return df
