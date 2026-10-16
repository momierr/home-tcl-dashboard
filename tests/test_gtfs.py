import zipfile
from datetime import date, datetime
from pathlib import Path

import pytest

from home_tcl_dashboard.gtfs import (
    WEEKDAYS,
    active_services,
    build_departures,
    gtfs_time,
)
from home_tcl_dashboard.realtime import Departure

SUNDAY = date(2026, 10, 11)


def calendar_row(service_id: str, **fields: str) -> dict[str, str]:
    """A weekly calendar row running on no day, unless days are given (sunday="1")."""
    row = {
        "service_id": service_id,
        "start_date": "20260101",
        "end_date": "20261231",
    }
    row.update({weekday: "0" for weekday in WEEKDAYS})
    row.update(fields)
    return row


def test_active_services_follows_the_weekly_calendar() -> None:
    calendar = [calendar_row("sun", sunday="1"), calendar_row("week", monday="1")]

    assert active_services(calendar, [], SUNDAY) == {"sun"}


def test_active_services_skips_services_outside_their_period() -> None:
    calendar = [calendar_row("old", sunday="1", end_date="20261010")]

    assert active_services(calendar, [], SUNDAY) == set()


def test_active_services_removes_a_service_on_a_holiday() -> None:
    calendar = [calendar_row("sun", sunday="1")]
    holiday = [{"service_id": "sun", "date": "20261011", "exception_type": "2"}]

    assert active_services(calendar, holiday, SUNDAY) == set()


def test_active_services_adds_a_service_on_a_date() -> None:
    extra = [{"service_id": "event", "date": "20261011", "exception_type": "1"}]

    assert active_services([], extra, SUNDAY) == {"event"}


def test_active_services_ignores_exceptions_on_other_dates() -> None:
    calendar = [calendar_row("sun", sunday="1")]
    other_day = [{"service_id": "sun", "date": "20261012", "exception_type": "2"}]

    assert active_services(calendar, other_day, SUNDAY) == {"sun"}


@pytest.mark.parametrize(
    "day, weekday",
    [(date(2026, 10, 12), "monday"), (SUNDAY, "sunday")],
)
def test_active_services_reads_the_english_weekday_column(
    day: date, weekday: str
) -> None:
    calendar = [calendar_row("svc", **{weekday: "1"})]
    assert active_services(calendar, [], day) == {"svc"}


def test_gtfs_time_on_the_service_day() -> None:
    assert gtfs_time(SUNDAY, "18:02:00") == datetime(2026, 10, 11, 18, 2)


def test_gtfs_time_after_midnight_is_the_next_day() -> None:
    assert gtfs_time(SUNDAY, "25:10:00") == datetime(2026, 10, 12, 1, 10)


def write_gtfs(path: Path, files: dict[str, str]) -> None:
    """Write a tiny GTFS zip: {file name: CSV content}."""
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def test_build_departures_keeps_running_trips_of_the_lines(tmp_path: Path) -> None:
    path = tmp_path / "gtfs.zip"
    days = ",".join(WEEKDAYS)
    write_gtfs(
        path,
        {
            "calendar.txt": f"service_id,{days},start_date,end_date\n"
            "sun,0,0,0,0,0,0,1,20260101,20261231\n"
            "mon,1,0,0,0,0,0,0,20260101,20261231\n",
            "calendar_dates.txt": "service_id,date,exception_type\n",
            "trips.txt": "route_id,service_id,trip_id\nA,sun,t1\nA,mon,t2\nC9,sun,t3\n",
            "stop_times.txt": "trip_id,departure_time,stop_id\n"
            "t1,18:02:00,30101\n"
            "t1,24:30:00,30103\n"
            "t2,18:05:00,30101\n"
            "t3,18:06:00,30101\n",
        },
    )

    departures = build_departures(path, SUNDAY, {"A"})

    assert departures == [
        Departure("A", "30101", datetime(2026, 10, 11, 18, 2), realtime=False),
        Departure("A", "30103", datetime(2026, 10, 12, 0, 30), realtime=False),
    ]
