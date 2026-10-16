from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import requests

from home_tcl_dashboard.alerts import Alert
from home_tcl_dashboard.grandlyon import GrandLyon
from home_tcl_dashboard.network import (
    Line,
    Platform,
    Point,
    parse_lines,
    parse_platform,
    parse_points,
    parse_traces,
)
from home_tcl_dashboard.realtime import Departure

LINE_LAYERS = ["tcllignemf_2_0_0", "tcllignetram_2_0_0", "tcllignebus_2_0_0"]
LINE_PROPERTIES = "code_ligne,sens,nom_destination,famille_transport,couleur_hex"
REGULAR_TRACES = "type_trace='NOM' AND code_type_ligne='REG'"
SCHEDULED_MODES = {"MET", "FUN"}
# Grand Lyon updates the passages once a minute: asking more often only adds a
# second of wait to every screen. Alerts change far less often.
PASSAGES_MAX_AGE = timedelta(seconds=30)
ALERTS_MAX_AGE = timedelta(minutes=5)


@dataclass
class LineSummary:
    code: str
    colour: str
    destinations: dict[str, str]


@dataclass
class StopSummary:
    platform: str
    name: str


@dataclass
class MapStop:
    platform: str
    name: str
    lat: float
    lon: float


@dataclass
class LineMap:
    colour: str
    trace: list[list[Point]]
    stops: list[MapStop]


@dataclass
class StopDetail:
    line: str
    colour: str
    platform_name: str
    destination: str
    departures: list[Departure]
    next_stops: list[str]
    remaining: int
    favourite: bool
    now: datetime
    stale: bool


@dataclass
class AlertsPage:
    mine: list[Alert]
    network: list[Alert]
    updated_at: datetime | None
    stale: bool


def load_geometry(
    client: GrandLyon,
) -> tuple[dict[str, Point], dict[tuple[str, str], list[list[Point]]]]:
    """Platform positions and line traces, for the line map (browse screen)."""
    positions = {
        row["id"]: parse_points(row["the_geom"])[0]
        for row in client.fetch_wfs("tclarret", "id,the_geom")
        if row["the_geom"]
    }
    line_rows = [
        row
        for layer in LINE_LAYERS
        for row in client.fetch_wfs(layer, "code_ligne,sens,the_geom", REGULAR_TRACES)
    ]
    return positions, parse_traces(line_rows)


def load_pictograms(client: GrandLyon, directory: Path) -> None:
    """Download the line pictograms once; without them the screens show badges."""
    try:
        client.download_pictograms(directory)
    except requests.RequestException:
        pass


def load_network(client: GrandLyon) -> tuple[dict[str, Platform], dict[str, Line]]:
    """Platforms by id and lines by code, from the WFS."""
    platform_rows = client.fetch_wfs("tclarret", "id,nom,desserte")
    platforms = {row["id"]: parse_platform(row) for row in platform_rows}

    line_rows: list[dict[str, str]] = []
    for layer in LINE_LAYERS:
        line_rows.extend(client.fetch_wfs(layer, LINE_PROPERTIES, REGULAR_TRACES))
    lines = parse_lines(line_rows)

    return platforms, lines
