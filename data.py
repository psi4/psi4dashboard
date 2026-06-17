"""Shared data loading and runtime state for the dashboard.

The data path is supplied on the command line at runtime, but Dash imports
page modules when the app is constructed. To bridge that gap, the entry point
loads the DataFrame and stashes it here with ``set_dataframe``; page layouts and
callbacks read it lazily via ``get_data`` at request time.
"""

import json

import pandas as pd

_dataframe = None


def set_dataframe(df):
    """Store the loaded DataFrame for pages to read later."""
    global _dataframe
    _dataframe = df


def get_data():
    """Return the DataFrame stored by ``set_dataframe`` (or None)."""
    return _dataframe


def get_dataframe():
    """Read timers.json file into DataFrame.
    """
    with open("timers.json") as f:
        payload = json.load(f)

        # Each entry in the "timers" array becomes a row, with its keys as columns.
    df = pd.json_normalize(payload["timers"])
    
    return df
