"""Timers page: line charts of a selected timer's metrics across tests, served at /timers."""

import dash

from metric_page import build_metric_page

dash.register_page(
    __name__,
    path="/timers",
    name="Timers",
    layout=build_metric_page(
        id_prefix="timers",
        title="Timers Dashboard",
        placeholder="Select a timer",
        select_column="timer_id",
        group_column="test_name",
        query_param="timer_name",
    ),
)
