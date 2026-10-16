from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class Departure:
    line: str
    platform: str
    time: datetime
    realtime: bool


def latest_estimates(passages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only the most recent estimate of each trip (coursetheorique)."""
    latest: dict[str, dict[str, Any]] = {}
    for passage in passages:
        trip = passage["coursetheorique"]
        if (
            trip not in latest
            or passage["last_update_fme"] > latest[trip]["last_update_fme"]
        ):
            latest[trip] = passage

    return list(latest.values())


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
