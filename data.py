"""Shared data loading and runtime state for the dashboard.

All data is read from the sibling ``psi4dashboard-data`` repo at the hardcoded
``DATA_DIR`` path. Dash imports page modules when the
app is constructed, so ``dashboard.create_app`` loads each dataset once at startup
and stashes it in a module global via ``set_timing_dataframe`` /
``set_scf_dataframe`` / ``set_parallelism_dataframe``; page layouts and callbacks
then read filtered slices lazily at request time.

Datasets (one DataFrame each; full column schemas live on the ``create_*_df``
parsers below):

- **timing** — one row per timer per test run; from ``timer.json``.
- **scf** — one row per (test run, SCF label); from ``scf_iterations.json``.
- **parallelism** — one row per timer per core count; from ``<test>.json.n<cores>.out``.

Cross-frame gotchas: timing and scf name the version column ``psi4_version``,
while parallelism uses ``version`` and adds ``cores`` (and carries no
``psi4_commit_hash``/``timer_path``).
"""

import json
import logging
from pathlib import Path
from packaging.version import Version

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path("../psi4dashboard-data/data/")

_timing_dataframe = None
_scf_dataframe = None
_parallelism_dataframe = None

# Column schema for each dataset. When every source file for a dataset is skipped,
# ``load_dataframe`` returns an empty DataFrame with these columns (rather than
# raising), so a loaded frame always exposes the full schema.
# Full per-column documentation lives on the ``create_*_df`` parsers.
TIMING_COLUMNS = [
    "timer_id", "psi4_version", "psi4_commit_hash", "test_name",
    "wall_time", "user_time", "system_time", "n_calls",
    "timer_name", "parent_id", "timer_path", "level",
]
SCF_COLUMNS = [
    "test_name", "psi4_version", "psi4_commit_hash", "optimization",
    "accelerator_raw", "label", "iterations", "correlation",
]
PARALLELISM_COLUMNS = [
    "test_name", "version", "cores", "timer_id", "timer_name", "parent_id",
    "level", "wall_time", "user_time", "system_time", "n_calls",
    "speedup",  # derived across files in load_parallelism_dataframe, not parsed
]


def load_dataframe(filename, df_creator, columns):
    """Build one DataFrame from every ``filename`` found under ``DATA_DIR``.

    Recursively globs ``DATA_DIR`` for ``filename`` (a plain name or a glob
    pattern), runs ``df_creator(path)`` on each match, and concatenates the
    results. ``df_creator`` returns a DataFrame, or ``None`` to skip a malformed
    or empty file. When every file is skipped, returns an empty DataFrame with
    ``columns`` (rather than raising); otherwise only the parsed frames are
    concatenated, so their column dtypes are preserved.
    """
    files = sorted(DATA_DIR.rglob(filename))

    dfs = []

    for file in files:
        df = df_creator(file)
        if (df is not None):
            dfs.append(df)

    if not dfs:
        logger.warning("No valid %r files under %s; returning an empty frame", filename, DATA_DIR)
        return pd.DataFrame(columns=columns)

    return pd.concat(dfs)


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


def get_timing_data():
    """Return the full, unfiltered timing DataFrame (see ``get_timing_slice`` for a slice)."""
    return _timing_dataframe


def get_scf_data():
    """Return the full SCF DataFrame."""
    return _scf_dataframe


def get_scf_accelerators(test_name):
    """Return one row per (version, accelerator) for a test's accelerator_raw.

    accelerator_raw ({scheme: iteration_count}) is duplicated across the
    label-exploded SCF rows, so collapse to one row per version before exploding
    the dict. ``create_scf_df`` requires a non-empty accelerator_raw on every
    loaded row, so no missing/empty guard is needed here. Sorted by version so
    the chart line follows it. Returns the (possibly empty) frame, or None when
    no SCF data is loaded.
    """
    df = get_scf_data()
    if df is None or df.empty:
        return df
    df = df[df["test_name"] == test_name]
    df = df.drop_duplicates(subset=["psi4_version"])[["test_name", "psi4_version", "accelerator_raw"]]
    df = df.reset_index(drop=True)          # explode_dict joins on index; keep it unique
    df = explode_dict(df, "accelerator_raw", "accelerator", "iterations")
    return df.sort_values("psi4_version", key=lambda x: x.map(Version))


def get_version_segments(df, value_column):
    """Total ``value_column`` per version, split into minor-version line segments.

    A single line across all versions would move just because the set of tests
    changes between versions, so the history is broken into one segment per
    consecutive minor-version step. The segment breakpoints are the first (lowest)
    version of each minor; each segment runs from one breakpoint to the next,
    inclusive, and captures any patch versions in between. Within a segment only tests
    present in *all* of its versions are counted, so the total is comparable across
    the segment; the total is the sum of ``value_column`` over those tests.

    The caller supplies the (already filtered) frame, so this works with any
    DataFrame carrying ``psi4_version``, ``test_name`` and ``value_column`` — see
    ``get_scf_iteration_segments`` and ``get_timing_wall_time_segments``.

    Returns a long-form frame (``psi4_version``, ``value_column``, ``segment``)
    sorted by version and ready for ``graph_group(color="segment")``, or the
    (possibly empty) frame itself when there is no data.
    """
    if df is None or df.empty:
        return df

    versions = sorted(df["psi4_version"].unique(), key=Version)

    # Breakpoints: the first version seen for each (major, minor). Since versions is
    # ascending, the first occurrence of a minor is its lowest version.
    breakpoints = []
    seen_minors = set()
    for v in versions:
        minor = (Version(v).major, Version(v).minor)
        if minor not in seen_minors:
            seen_minors.add(minor)
            breakpoints.append(v)

    rows = []
    for b_a, b_b in zip(breakpoints, breakpoints[1:]):
        seg_versions = [v for v in versions if Version(b_a) <= Version(v) <= Version(b_b)]
        common = set.intersection(
            *(set(df.loc[df["psi4_version"] == v, "test_name"]) for v in seg_versions)
        )
        segment = f"{b_a} → {b_b}"
        for v in seg_versions:
            total = df[(df["psi4_version"] == v) & (df["test_name"].isin(common))][value_column].sum()
            rows.append({"psi4_version": v, value_column: total, "segment": segment})

    out = pd.DataFrame(rows, columns=["psi4_version", value_column, "segment"])
    return out.sort_values("psi4_version", key=lambda x: x.map(Version))


def get_scf_iteration_segments():
    """Return total SCF iterations per version as minor-version segments.

    Sums ``iterations`` over every SCF label of every test (labels are disjoint,
    so nothing is counted twice). See ``get_version_segments`` for the
    segmentation rule and the returned shape.
    """
    return get_version_segments(get_scf_data(), "iterations")


def get_timing_wall_time_segments():
    """Return total wall time per version as minor-version segments.

    Only level-0 (root) timers are summed: a parent timer's ``wall_time`` already
    includes its children, so summing every level would count each nested region
    once per ancestor above it. See ``get_version_segments`` for the segmentation
    rule and the returned shape.
    """
    df = get_timing_data()
    if df is None or df.empty:
        return df
    return get_version_segments(df[df["level"] == 0], "wall_time")


def get_parallelism_data():
    """Return the full, unfiltered parallelism DataFrame (see ``get_parallelism_slice``)."""
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
    return sorted(df["version"].dropna().unique(), key=Version)


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


def get_timing_slice(level=None, column=None, value=None):
    """Return the stored rows narrowed to the requested slice (or None).

    With no arguments the full DataFrame is returned. ``level`` keeps only rows
    at that hierarchy level; ``column`` keeps only rows where that column equals
    ``value`` (so a ``None`` value yields an empty frame). The result is sorted
    by ``psi4_version`` so chart lines follow it.
    """
    df = get_timing_data()
    if df is None:
        return None
    if level is not None:
        df = df[df["level"] == level]
    if column is not None:
        df = df[df[column] == value]
    return df.sort_values("psi4_version", key=lambda x: x.map(Version))


def get_timing_levels():
    """Return the sorted distinct hierarchy levels, for the slider."""
    df = get_timing_slice()
    return sorted(df["level"].dropna().unique()) if df is not None else []


def get_timing_options(column, level):
    """Return the sorted distinct values of ``column`` among rows at ``level``.

    Used to populate the dropdown of timer/test page for a given slider level.
    """
    df = get_timing_slice(level=level)
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


def get_timing_children(parent_id, test_name):
    """Return the child rows of ``parent_id`` within ``test_name``, by version.

    Children are rows naming this timer as their parent; they sit one level
    deeper. Used to render a filled-area breakdown for non-leaf timers. Returns
    an empty frame for a leaf timer (and ``None`` when no data is loaded).
    """
    df = get_timing_data()
    if df is None:
        return None
    df = df[(df["parent_id"] == parent_id) & (df["test_name"] == test_name)]
    return df.sort_values("psi4_version", key=lambda x: x.map(Version))


def create_timer_df(file: Path):
    """Parse one ``timer.json`` into a per-timer DataFrame, or ``None`` to skip.

    Returns ``None`` (so ``load_dataframe`` drops the file) when the payload is
    missing required keys (``timers``, ``psi4_version``, ``psi4_commit_hash``) or
    has no timers. Otherwise flattens the ``timers`` dict into one row per timer,
    tags each with ``test_name`` (the file's grandparent dir), and names the id
    column ``timer_id``.

    Columns:

        timer_id         str      ;-nested hierarchy id (e.g. "HF: Form G;JK: JK")
        psi4_version     str
        psi4_commit_hash str      UNUSED downstream (only a required key gating the parse)
        test_name        str
        wall_time        float64  seconds
        user_time        float64  seconds
        system_time      float64  seconds
        n_calls          int64
        timer_name       str      leaf segment of timer_id
        parent_id        object   str, or None for a root timer
        timer_path       object   UNUSED downstream
        level            int64    nesting depth (count of ';')
    """
    with open(file) as f:
        payload = json.load(f)
    
    required_keys = {'timers', 'psi4_version', 'psi4_commit_hash'}

    if not (required_keys <= payload.keys()):
        logger.debug("Skipping %s: missing required keys %s", file, required_keys - payload.keys())
        return

    if (len(payload["timers"]) == 0):
        logger.debug("Skipping %s: no timer data", file)
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
    return load_dataframe("timer.json", create_timer_df, TIMING_COLUMNS)


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
    """Parse one ``scf_iterations.json`` into a per-label DataFrame, or ``None`` to skip.

    Returns ``None`` (so ``load_dataframe`` drops the file) when the payload lacks
    the required keys (``scf``, ``psi4_version``, ``psi4_commit_hash``) or its
    ``scf`` block has no per-label iteration data (``iterations_by_label``) or no
    ``accelerator_raw`` breakdown. Otherwise flattens the ``scf`` block and
    explodes ``iterations_by_label`` into one row per (label, iterations) via
    ``explode_dict``, dropping bookkeeping columns (git dirty/branch,
    total_iterations, accelerators).

    Requiring ``accelerator_raw`` here means every loaded row carries a usable
    accelerator dict, so ``get_scf_accelerators`` can explode it without
    re-checking for missing/empty values.

    Columns:

        test_name        str
        psi4_version     str
        psi4_commit_hash str      UNUSED downstream
        optimization     object   UNUSED downstream
        accelerator_raw  object   dict {accelerator_scheme: iteration_count};
                                  exploded by ``get_scf_accelerators`` for the
                                  SCF page's accelerator breakdown
        label            object   SCF label this row was exploded to
        iterations       int64
        correlation      object   UNUSED downstream
    """
    with open(path) as f:
        payload = json.load(f)

    required_keys = {"scf", "psi4_version", "psi4_commit_hash"}
    if not (required_keys <= payload.keys()):
        logger.debug("Skipping %s: missing required keys %s", path, required_keys - payload.keys())
        return

    scf_block = payload["scf"]
    if not isinstance(scf_block, dict) or not scf_block.get("iterations_by_label") or not scf_block.get("accelerator_raw"):
        logger.debug("Skipping %s: no per-label SCF iteration or accelerator data", path)
        return

    raw_df = pd.DataFrame([payload]) # must keep brackets to read it as single entry

    scf = pd.json_normalize(raw_df['scf'], max_level=0)

    scf = scf.drop(["total_iterations", "accelerators"], axis=1, errors="ignore")

    clean_df = pd.concat([raw_df.drop(columns=["scf", "psi4_git_dirty", "psi4_branch"], errors="ignore"), scf],axis=1)

    final_df = explode_dict(clean_df, "iterations_by_label", "label", "iterations")

    return final_df


def load_scf_dataframe():
    """Read scf_iterations.json files from data repository into DataFrame.
    """
    return load_dataframe("scf_iterations.json", create_scf_df, SCF_COLUMNS)


def create_parallelism_df(path: Path):
    """Parse one QCSchema ``<test>.json.n<cores>.out`` file into a timer DataFrame, or ``None`` to skip.

    Returns ``None`` (so ``load_dataframe`` drops the file) when the filename
    doesn't match the convention or the payload lacks ``provenance.version`` or
    ``native_files['timer.json']`` timer data. ``test_name`` and ``cores`` come
    from the filename (``bz-fnocc.json.n8.out`` -> test ``bz-fnocc``, 8 cores);
    ``version`` from ``provenance.version``; and the per-timer rows from the
    embedded ``native_files['timer.json']``. ``parent_id``, ``timer_name`` and
    ``level`` are derived from the ``;``-nested ``timer_id``.

    Columns:

        test_name   str
        version     str      NOTE: 'version', not 'psi4_version'
        cores       int64    parsed from the filename
        timer_id    str      ;-nested hierarchy id
        timer_name  str
        parent_id   str      None for a root timer
        level       int64    nesting depth (count of ';')
        wall_time   float64  seconds
        user_time   float64  seconds -- UNUSED (the parallelism page plots wall_time only)
        system_time float64  seconds -- UNUSED (the parallelism page plots wall_time only)
        n_calls     float64
    """
    f_name = path.as_posix().rsplit("/", 1)[-1]
    test_name = f_name.split('.', 1)[0] 
    # cores come from the ".n<cores>" segment; skip names that don't match the
    # <test>.json.n<cores>.out convention
    name_parts = f_name.rsplit('.', 2)
    if len(name_parts) < 3 or not name_parts[1].startswith('n') or not name_parts[1][1:].isdigit():
        logger.debug("Skipping %s: filename does not match <test>.json.n<cores>.out", path)
        return
    n_cores = int(name_parts[1][1:])

    with open(path) as f:
        payload = json.load(f)

    version = (payload.get('provenance') or {}).get('version') # version number from the file

    data = (payload.get('native_files') or {}).get('timer.json') # timer.json from the file
    if version is None or not data:
        logger.debug("Skipping %s: missing provenance version or timer data", path)
        return

    # turn the timer.json into a pandas dataframe, and fix the layout of the dataframe
    df = pd.DataFrame(data).transpose().reset_index()

    if df.shape[1] != 5:
        logger.debug("Skipping %s: timer entries lack the expected 4 metric fields", path)
        return
    
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

    Also adds the derived ``speedup`` column: within each (test_name, version,
    timer_id) group, the 1-core ``wall_time`` divided by the row's ``wall_time``
    (so 1.0 at one core, and ideally ``cores`` at ``cores``). NaN for timers
    with no 1-core run. Derived here rather than in ``create_parallelism_df``
    because a row's 1-core baseline lives in a different source file.
    """
    df = load_dataframe("*.json.n*", create_parallelism_df, PARALLELISM_COLUMNS)
    if df.empty:
        return df
    baseline = df["wall_time"].where(df["cores"] == 1)
    df["speedup"] = (
        df.assign(baseline=baseline)
        .groupby(["test_name", "version", "timer_id"])["baseline"]
        .transform("first")  # the group's 1-core wall_time (first skips NaN)
        / df["wall_time"]
    )
    return df