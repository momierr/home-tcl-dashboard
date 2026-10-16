from datetime import date

import pytest

from home_tcl_dashboard.gtfs import WEEKDAYS, active_services

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
