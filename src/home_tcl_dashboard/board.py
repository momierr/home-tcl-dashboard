from dataclasses import dataclass
from datetime import datetime

from home_tcl_dashboard.network import Line, Platform
from home_tcl_dashboard.realtime import Departure, next_departures


@dataclass
class Favourite:
    line: str
    sens: str
    platform: str


@dataclass
class Card:
    line: str
    platform_name: str
    destination: str
    departures: list[Departure]


def build_card(
    favourite: Favourite,
    platforms: dict[str, Platform],
    lines: dict[str, Line],
    departures: list[Departure],
    now: datetime,
) -> Card:
    """Everything one home-screen card shows, for one favourite."""
    platform = platforms[favourite.platform]
    line = lines[favourite.line]
    return Card(
        line=line.code,
        platform_name=platform.name,
        destination=line.destinations[favourite.sens],
        departures=next_departures(departures, line.code, now),
    )
