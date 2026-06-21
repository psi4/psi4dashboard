"""Tests page: per-test line charts of timer metrics, served at /tests."""

import dash

from metric_page import build_metric_page

dash.register_page(
    __name__,
    path="/tests",
    name="Tests",
    layout=build_metric_page(
        id_prefix="tests",
        title="Tests Dashboard",
        placeholder="Select a test",
        select_column="test_name",
        group_column="timer_id",
        query_param="test_name",
    ),
)
