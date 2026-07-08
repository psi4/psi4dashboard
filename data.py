"""Shared data loading and runtime state for the dashboard.

The data path is supplied on the command line at runtime, but Dash imports
page modules when the app is constructed. To bridge that gap, the entry point
loads the DataFrame and stashes it here with ``set_timing_dataframe``; page layouts and
callbacks read filtered slices of it lazily at request time.
"""

import json
from pathlib import Path
from packaging.version import Version

import pandas as pd

DATA_DIR = Path("../psi4dashboard-data/data/") ## change it as appopriate

_timing_dataframe = None
_scf_dataframe = None
_parallelism_dataframe = None


def load_dataframe(filename, df_creator):
    """load dataframe from all files of the given filename"""
    files = sorted(DATA_DIR.rglob(filename))

    dfs = []

    for file in files:
        df = df_creator(file)
        if (df is not None):
            dfs.append(df)

    df = pd.concat(dfs)

    return df


def set_timing_dataframe(df):
    """Store the loaded timings DataFrame for pages to read later."""
    global _timing_dataframe
    _timing_dataframe = df


def set_scf_dataframe(df):
    """Store the loaded scf DataFrame for pages to read later."""
    global _scf_dataframe
    _scf_dataframe = df

def set_parallelism_dataframe(df):
    """Store the loaded parallelism DataFrame for pages to read later."""
    global _parallelism_dataframe
    _parallelism_dataframe = df


def get_scf_data():
    return _scf_dataframe


def get_parallelism_data():
    return _parallelism_dataframe


def get_parallelism_levels():
    """Return the sorted distinct timer levels in the parallelism data."""
    df = get_parallelism_data()
    if df is None or df.empty:
        return []
    return sorted(df["level"].dropna().unique())


def get_parallelism_versions():
    """Return the sorted distinct Psi4 versions in the parallelism data."""
    df = get_parallelism_data()
    if df is None or df.empty:
        return []
    return sorted(df["version"].dropna().unique())


def get_parallelism_tests(version):
    """Return the sorted distinct test names present in ``version``.

    Used to populate the test dropdown for the selected version, so it only
    lists tests that actually have parallelism data there.
    """
    df = get_parallelism_data()
    if df is None or df.empty:
        return []
    if version is not None:
        df = df[df["version"] == version]
    return sorted(df["test_name"].dropna().unique())


def get_parallelism_slice(level=None, test_name=None, version=None):
    """Return the parallelism rows narrowed to the requested slice (or None).

    Each supplied filter (``version``, ``test_name``, ``level``) is applied in
    turn; the result is sorted by ``cores`` so chart lines follow the core
    count on the x-axis.
    """
    df = get_parallelism_data()
    if df is None or df.empty:
        return df
    if version is not None:
        df = df[df["version"] == version]
    if test_name is not None:
        df = df[df["test_name"] == test_name]
    if level is not None:
        df = df[df["level"] == level]
    return df.sort_values("cores")


def get_parallelism_children(parent_id, test_name, version):
    """Return the child rows of ``parent_id`` within a test/version, by cores.

    Children name this timer as their parent and sit one level deeper; used to
    render a filled-area breakdown for non-leaf timers. Returns an empty frame
    for a leaf timer (and ``None`` when no data is loaded).
    """
    df = get_parallelism_data()
    if df is None or df.empty:
        return df
    mask = (df["parent_id"] == parent_id) & (df["test_name"] == test_name)
    if version is not None:
        mask &= df["version"] == version
    return df[mask].sort_values("cores")


def get_timing_data(level=None, column=None, value=None):
    """Return the stored rows narrowed to the requested slice (or None).

    With no arguments the full DataFrame is returned. ``level`` keeps only rows
    at that hierarchy level; ``column`` keeps only rows where that column equals
    ``value`` (so a ``None`` value yields an empty frame). The result is sorted
    by ``version`` so chart lines follow it.
    """
    df = _timing_dataframe
    if df is None:
        return None
    if level is not None:
        df = df[df["level"] == level]
    if column is not None:
        df = df[df[column] == value]
    return df.sort_values("psi4_version", key=lambda x: x.map(Version))


def get_levels():
    """Return the sorted distinct hierarchy levels, for the slider."""
    df = get_timing_data()
    return sorted(df["level"].dropna().unique()) if df is not None else []


def get_options(column, level):
    """Return the sorted distinct values of ``column`` among rows at ``level``.

    Used to populate the dropdown for a given slider level.
    """
    df = get_timing_data(level=level)
    return sorted(df[column].unique()) if df is not None else []


def get_groups(df, group_column):
    """Partition ``df`` into chart-ready groups for rendering.

    ``df`` is partitioned by ``group_column`` into ``(key, group)`` pairs (one
    per card). Returns an empty list when there is no data. The caller supplies
    the (already filtered and sorted) frame, so this works with any DataFrame.
    """
    if df is None or df.empty:
        return []
    return list(df.groupby(group_column))


def get_children(parent_id, test_name):
    """Return the child rows of ``parent_id`` within ``test_name``, by version.

    Children are rows naming this timer as their parent; they sit one level
    deeper. Used to render a filled-area breakdown for non-leaf timers. Returns
    an empty frame for a leaf timer (and ``None`` when no data is loaded).
    """
    df = _timing_dataframe
    if df is None:
        return None
    df = df[(df["parent_id"] == parent_id) & (df["test_name"] == test_name)]
    return df.sort_values("psi4_version", key=lambda x: x.map(Version))


def create_timer_df(file: Path):
    with open(file) as f:
        payload = json.load(f)
    
    required_keys = {'timers', 'psi4_version', 'psi4_commit_hash'}

    if payload.keys() < required_keys:
        #print(f"not all required keys are in {file}")
        return
    
    if (len(payload["timers"]) == 0):
        #print(f"no timing data in {file}")
        return

    payload["test_name"] = file.parents[1].name

    raw_df = pd.DataFrame(payload)

    timings = pd.json_normalize(raw_df['timers'])

    final_df = pd.concat([raw_df.drop(columns=["timers"]), timings],axis=1).reset_index()

    final_df.columns.values[0] = "timer_id"

    return final_df


def load_timing_dataframe():
    """Read timer.json files from data repository into DataFrame.
    """
    return load_dataframe("timer.json", create_timer_df)


def explode_dict(df, col, key_name, value_name):
    """ Breaks down the ``col`` with dictionary entry into two columns: ``key_name``
    and ``value_name``. The remaining columns are duplicated for dicts with multiple
    entries
    """
    m = pd.DataFrame([*df[col]], df.index).stack()\
          .rename_axis([None, key_name]).reset_index(1, name=value_name)

    out = df.drop(col, axis=1).join(m)

    return out.dropna()


def create_scf_df(path: Path):
    with open(path) as f:
        payload = json.load(f)

    payload

    raw_df = pd.DataFrame([payload]) # must keep brackets to read it as single entry

    scf = pd.json_normalize(raw_df['scf'], max_level=0)

    scf = scf.drop(["total_iterations", "accelerators"], axis=1)

    clean_df = pd.concat([raw_df.drop(columns=["scf", "psi4_git_dirty", "psi4_branch"]), scf],axis=1)

    final_df = explode_dict(clean_df, "iterations_by_label", "label", "iterations")

    return final_df


def load_scf_dataframe():
    """Read scf_iterations.json files from data repository into DataFrame.
    """
    return load_dataframe("scf_iterations.json", create_scf_df)


def create_parallelism_df(path: Path):
    f_name = path.as_posix().rsplit("/", 1)[-1]
    test_name = f_name.split('.', 1)[0] 
    n_cores = int(f_name.rsplit('.', 2)[1][1:])

    with open(path) as f:
        payload = json.load(f)

    version = payload['provenance']['version'] # get version number from the file

    data = payload['native_files']['timer.json'] # get timer.json from the file

    # turn the timer.json into a pandas dataframe, and fix the layout of the dataframe
    df = pd.DataFrame(data).transpose().reset_index()
    
    # required to rename timer_id column 
    df.columns = ['timer_id','wall_time','user_time','system_time','n_calls']

    # add test_name, version, and n_cores
    df['test_name'] = test_name
    df['version'] = version
    df['cores'] = n_cores
    
    # split timer_id to get parent_id and timer_name columns
    parts = df['timer_id'].str.rpartition(';')
    df['parent_id'] = parts[0].where(parts[1] == ';', None)
    df['timer_name'] = parts[2]

    # add level column
    df['level'] = df['timer_id'].str.count(";")

    # return dataframe with columns sorted in a sensible order
    return df[['test_name', 'version', 'cores', 'timer_id', 'timer_name', 'parent_id', 'level', 'wall_time', 'user_time', 'system_time', "n_calls"]]

def load_parallelism_dataframe():
    """Read all parallelism files from data repository into DataFrame.
    """
    return load_dataframe("*.json.n*", create_parallelism_df)