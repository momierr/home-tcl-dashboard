from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass
class Departure:
    line: str
    platform: str
    time: datetime
    realtime: bool


def latest_estimates(passages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only the most recent estimate of each trip (coursetheorique) at each stop."""
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for passage in passages:
        trip = (passage["id"], passage["coursetheorique"])
        if (
            trip not in latest
            or passage["last_update_fme"] > latest[trip]["last_update_fme"]
        ):
            latest[trip] = passage

    return list(latest.values())


def drop_doubled_schedules(
    departures: list[Departure], window: timedelta = timedelta(minutes=1)
) -> list[Departure]:
    """Drop a scheduled departure when a real-time one of the same line, at the
    same stop, is within `window`: Grand Lyon sometimes gives the live bus
    another trip id, and leaves the scheduled trip it replaces in the list."""
    live = [departure for departure in departures if departure.realtime]
    return [
        departure
        for departure in departures
        if departure.realtime
        or not any(
            other.line == departure.line
            and other.platform == departure.platform
            and abs(other.time - departure.time) <= window
            for other in live
        )
    ]


def parse_departure(passage: dict[str, Any]) -> Departure:
    return Departure(
        line=passage["ligne"],
        platform=passage["id"],
        time=datetime.fromisoformat(passage["heurepassage"]),
        realtime=passage["type"] == "E",
    )


def next_departures(
    departures: list[Departure], line: str, now: datetime, n: int = 3
) -> list[Departure]:
    upcoming = [
        departure
        for departure in departures
        if departure.line == line and departure.time >= now
    ]
    return sorted(upcoming, key=lambda departure: departure.time)[:n]
