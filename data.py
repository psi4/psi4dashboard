"""Shared data loading and runtime state for the dashboard.

The data path is supplied on the command line at runtime, but Dash imports
page modules when the app is constructed. To bridge that gap, the entry point
loads the DataFrame and stashes it here with ``set_dataframe``; page layouts and
callbacks read filtered slices of it lazily at request time.
"""

import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path("data")

_dataframe = None
_scf_labels = None
_scf_accels = None


def set_dataframe(df):
    """Store the loaded DataFrame for pages to read later."""
    global _dataframe
    _dataframe = df

def get_scf_labels():
    return _scf_labels

def get_scf_accels():
    return _scf_accels

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


def get_children(parent_id, test_name):
    """Return the child rows of ``parent_id`` within ``test_name``, by version.

    Children are rows naming this timer as their parent; they sit one level
    deeper. Used to render a filled-area breakdown for non-leaf timers. Returns
    an empty frame for a leaf timer (and ``None`` when no data is loaded).
    """
    df = _dataframe
    if df is None:
        return None
    df = df[(df["parent_id"] == parent_id) & (df["test_name"] == test_name)]
    return df.sort_values("version")


def get_dataframe():
    """Read timers.json file into DataFrame.
    """
    with open("timers.json") as f:
        payload = json.load(f)

        # Each entry in the "timers" array becomes a row, with its keys as columns.
    df = pd.json_normalize(payload["timers"])

    return df

def set_scf_labels(df):
    global _scf_labels
    data = explode_dict(df, "scf.iterations_by_label", "label", "iterations")
    _scf_labels = data[["test_name", "version", "label", "iterations"]]

def set_scf_accels(df):
    global _scf_accels
    data = explode_dict(df, "scf.accelerators", "accelerator", "iterations")
    _scf_accels = data[["test_name", "version", "accelerator", "iterations"]]


def load_scf_iterations(data_dir=DATA_DIR):
    """Return one DataFrame combining all scf_iterations.json files.

    Walks ``data_dir`` for every ``scf_iterations.json``, normalizes the nested
    JSON into flat columns (only the first level), and tags each row with
    ``version`` = the name of the directory immediately containing the file.
    """
    rows = []
    for path in sorted(data_dir.glob("**/scf_iterations.json")):
        with open(path) as f:
            payload = json.load(f)
        row = pd.json_normalize(payload, max_level=1)
        row["version"] = path.parent.name
        rows.append(row)

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def explode_dict(df, col, key_name, value_name):
    """ Breaks down the ``col`` with dictionary entry into two columns: ``key_name``
    and ``value_name``. The remaining columns are duplicated for dicts with multiple
    entries
    """
    m = pd.DataFrame([*df[col]], df.index).stack()\
          .rename_axis([None, key_name]).reset_index(1, name=value_name)

    out = df.drop(col, axis=1).join(m)

    return out.dropna()
