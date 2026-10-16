from datetime import datetime
from typing import Any

from home_tcl_dashboard.realtime import (
    Departure,
    latest_estimates,
    next_departures,
    parse_departure,
)


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


def test_parse_departure_realtime_true() -> None:
    assert parse_departure(dummy_passage(type="E")) == Departure(
        line="T2",
        platform="32103",
        time=datetime(2026, 10, 15, 23, 55, 44),
        realtime=True,
    )


def test_parse_departure_realtime_false() -> None:
    assert parse_departure(dummy_passage(type="T")) == Departure(
        line="T2",
        platform="32103",
        time=datetime(2026, 10, 15, 23, 55, 44),
        realtime=False,
    )


def dummy_departure(**fields: Any) -> Departure:
    departure = Departure(
        line="T2",
        platform="32103",
        time=datetime(2026, 10, 15, 23, 55),
        realtime=True,
    )
    for name, value in fields.items():
        setattr(departure, name, value)
    return departure


NOW = datetime(2026, 10, 15, 23, 50)


def test_next_departures_keeps_only_the_line() -> None:
    t1 = dummy_departure(line="T1")
    t2 = dummy_departure(line="T2")

    assert next_departures([t1, t2], "T2", NOW) == [t2]


def test_next_departures_skips_past_departures() -> None:
    past = dummy_departure(time=datetime(2026, 10, 15, 23, 45))
    upcoming = dummy_departure(time=datetime(2026, 10, 15, 23, 55))

    assert next_departures([past, upcoming], "T2", NOW) == [upcoming]


def test_next_departures_sorts_by_time() -> None:
    late = dummy_departure(time=datetime(2026, 10, 15, 23, 58))
    early = dummy_departure(time=datetime(2026, 10, 15, 23, 52))
    middle = dummy_departure(time=datetime(2026, 10, 15, 23, 55))

    assert next_departures([late, early, middle], "T2", NOW) == [early, middle, late]


def test_next_departures_keeps_only_n() -> None:
    departures = [
        dummy_departure(time=datetime(2026, 10, 15, 23, minute))
        for minute in [59, 51, 57, 53, 55]
    ]

    result = next_departures(departures, "T2", NOW, n=3)

    assert [d.time.minute for d in result] == [51, 53, 55]


def test_next_departures_keeps_departure_at_now() -> None:
    at_now = dummy_departure(time=NOW)

    assert next_departures([at_now], "T2", NOW) == [at_now]
