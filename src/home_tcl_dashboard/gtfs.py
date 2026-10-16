import csv
import io
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from datetime import date, datetime, time, timedelta
from pathlib import Path

from home_tcl_dashboard.realtime import Departure

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
    calendar: Iterable[dict[str, str]],
    calendar_dates: Iterable[dict[str, str]],
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


def gtfs_time(day: date, hms: str) -> datetime:
    """'25:10:00' on service day 2026-10-16 -> 2026-10-17 01:10:00."""
    hours, minutes, seconds = (int(part) for part in hms.split(":"))
    midnight = datetime.combine(day, time())
    return midnight + timedelta(hours=hours, minutes=minutes, seconds=seconds)


def read_csv(archive: zipfile.ZipFile, name: str) -> Iterator[dict[str, str]]:
    """Rows of a CSV file inside the zip, streamed (never fully loaded in memory)."""
    with archive.open(name) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"))


def build_departures(path: Path, day: date, lines: set[str]) -> list[Departure]:
    """Scheduled departures of `lines` for the service day `day`."""
    with zipfile.ZipFile(path) as archive:
        services = active_services(
            read_csv(archive, "calendar.txt"),
            read_csv(archive, "calendar_dates.txt"),
            day,
        )
        trip_lines = {
            row["trip_id"]: row["route_id"]
            for row in read_csv(archive, "trips.txt")
            if row["service_id"] in services and row["route_id"] in lines
        }
        departures = []
        for row in read_csv(archive, "stop_times.txt"):
            line = trip_lines.get(row["trip_id"])
            if line is not None:
                departures.append(
                    Departure(
                        line=line,
                        platform=row["stop_id"],
                        time=gtfs_time(day, row["departure_time"]),
                        realtime=False,
                    )
                )
    return departures


def stop_orders(path: Path, lines: set[str]) -> dict[tuple[str, str], list[str]]:
    """(line, sens) -> platform ids of its longest trip, in travel order."""
    with zipfile.ZipFile(path) as archive:
        trip_keys = {
            row["trip_id"]: (
                row["route_id"],
                "A" if row["direction_id"] == "0" else "R",
            )
            for row in read_csv(archive, "trips.txt")
            if row["route_id"] in lines
        }
        sizes = Counter(
            row["trip_id"]
            for row in read_csv(archive, "stop_times.txt")
            if row["trip_id"] in trip_keys
        )
        longest: dict[tuple[str, str], str] = {}
        for trip_id, size in sizes.items():
            key = trip_keys[trip_id]
            if key not in longest or size > sizes[longest[key]]:
                longest[key] = trip_id
        chosen = {trip_id: key for key, trip_id in longest.items()}
        stops: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
        for row in read_csv(archive, "stop_times.txt"):
            direction = chosen.get(row["trip_id"])
            if direction is not None:
                stops[direction].append((int(row["stop_sequence"]), row["stop_id"]))
    return {key: [stop for _, stop in sorted(rows)] for key, rows in stops.items()}
