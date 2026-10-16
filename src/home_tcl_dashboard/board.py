from dataclasses import dataclass
from datetime import datetime

from home_tcl_dashboard.alerts import Alert
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
    disrupted: bool


def build_card(
    favourite: Favourite,
    platforms: dict[str, Platform],
    lines: dict[str, Line],
    departures: list[Departure],
    alerts: list[Alert],
    now: datetime,
) -> Card:
    """Everything one home-screen card shows, for one favourite."""
    platform = platforms[favourite.platform]
    line = lines[favourite.line]
    here = [d for d in departures if d.platform == platform.id]
    return Card(
        line=line.code,
        platform_name=platform.name,
        destination=line.destinations[favourite.sens],
        departures=next_departures(here, line.code, now),
        disrupted=any(
            alert.line == line.code and alert.kind == "Perturbation" for alert in alerts
        ),
    )


@dataclass
class Banner:
    line: str
    title: str
    count: int


@dataclass
class Board:
    cards: list[Card]
    banner: Banner | None
    now: datetime
    updated_at: datetime | None
    stale: bool


def build_banner(favourites: list[Favourite], alerts: list[Alert]) -> Banner | None:
    favourite_lines = {favourite.line for favourite in favourites}
    mine = [alert for alert in alerts if alert.line in favourite_lines]
    if not mine:
        return None
    worst = min(mine, key=lambda alert: alert.severity)
    return Banner(line=worst.line, title=worst.title, count=len(mine))
