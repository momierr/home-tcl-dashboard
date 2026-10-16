from datetime import date

WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def active_services(
    calendar: list[dict[str, str]],
    calendar_dates: list[dict[str, str]],
    day: date,
) -> set[str]:
    """Service ids running on `day`: weekly calendar, then added (1) / removed (2)."""
    ymd = day.strftime("%Y%m%d")
    weekday = WEEKDAYS[day.weekday()]  # not strftime("%A"): it depends on the locale
    active = {
        row["service_id"]
        for row in calendar
        if row[weekday] == "1" and row["start_date"] <= ymd <= row["end_date"]
    }
    for row in calendar_dates:
        if row["date"] == ymd:
            if row["exception_type"] == "1":
                active.add(row["service_id"])
            else:
                active.discard(row["service_id"])
    return active
