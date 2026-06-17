#!/usr/bin/env python3
"""Find all 'timer.json' files within a directory and its subdirectories."""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def load_timer_frame():
    """Reads timers.json file into a DataFrame.

    Returns the DataFrame.
    """
    with open("timers.json") as f:
        payload = json.load(f)

        # Each entry in the "timers" array becomes a row, with its keys as columns.
    df = pd.json_normalize(payload["timers"])
    
    return df


def main():
    df = load_timer_frame()
    print(df.dropna().head())


if __name__ == "__main__":
    main()
