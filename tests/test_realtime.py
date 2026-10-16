from typing import Any

from home_tcl_dashboard.realtime import latest_estimates


def dummy_passage(**fields: Any) -> dict[str, Any]:
    passage = {
        "id": "32103",
        "ligne": "T2",
        "heurepassage": "2026-10-15 23:55:44",
        "type": "E",
        "coursetheorique": "trip-1",
        "last_update_fme": "2026-10-15 23:52:01",
    }
    passage.update(fields)
    return passage


def test_latest_estimates_keeps_most_recent_update() -> None:
    old = dummy_passage(last_update_fme="2026-10-15 23:50:00", heurepassage="old")
    new = dummy_passage(last_update_fme="2026-10-15 23:52:00", heurepassage="new")

    assert latest_estimates([new, old]) == [new]


def test_latest_estimates_keeps_distinct_trips() -> None:
    first = dummy_passage(coursetheorique="trip-1")
    second = dummy_passage(coursetheorique="trip-2")

    assert latest_estimates([first, second]) == [first, second]


def test_latest_estimates_empty() -> None:
    assert latest_estimates([]) == []
