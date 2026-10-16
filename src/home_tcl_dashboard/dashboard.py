from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Self

import requests

from home_tcl_dashboard.alerts import Alert, active_alerts, parse_alert
from home_tcl_dashboard.board import Board, Favourite, build_banner, build_card
from home_tcl_dashboard.cache import LastGood
from home_tcl_dashboard.favourites import (
    favourite_errors,
    load_favourites,
    save_favourites,
)
from home_tcl_dashboard.grandlyon import GrandLyon
from home_tcl_dashboard.gtfs import build_departures, stop_orders
from home_tcl_dashboard.network import (
    Line,
    Platform,
    Point,
    lines_of_mode,
    parse_lines,
    parse_platform,
    parse_points,
    parse_traces,
    timeline,
)
from home_tcl_dashboard.realtime import (
    Departure,
    drop_doubled_schedules,
    latest_estimates,
    next_departures,
    parse_departure,
)

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


class NotFound(Exception):
    """An unknown line, direction or stop: the route turns it into a 404."""


class InvalidFavourites(Exception):
    """Favourites that fail favourite_errors; args[0] is the list of errors."""


class Dashboard:
    """Everything the screens show: the network, the timetable, the real-time
    and alert caches, and the favourites. Knows nothing of HTTP."""

    def __init__(
        self,
        client: GrandLyon,
        data_dir: Path,
        platforms: dict[str, Platform],
        lines: dict[str, Line],
        positions: dict[str, Point],
        traces: dict[tuple[str, str], list[list[Point]]],
    ) -> None:
        self.client = client
        self.platforms = platforms
        self.lines = lines
        self.positions = positions
        self.traces = traces
        self.gtfs_path = data_dir / "GTFS_TCL.ZIP"
        self.fav_path = data_dir / "favourites.json"
        self.favourites = load_favourites(self.fav_path)
        self.scheduled: list[Departure] = []
        self.scheduled_for: date | None = None
        self.passages = LastGood(PASSAGES_MAX_AGE)
        self.alerts = LastGood(ALERTS_MAX_AGE)

    @classmethod
    def load(cls, client: GrandLyon, data_dir: Path) -> Self:
        """Download what the screens need (WFS, GTFS, pictograms), at startup."""
        platforms, lines = load_network(client)
        load_pictograms(client, data_dir / "pictos")
        positions, traces = load_geometry(client)
        dashboard = cls(client, data_dir, platforms, lines, positions, traces)
        dashboard.refresh_timetable(date.today())
        dashboard._load_stop_orders()
        return dashboard

    def _load_stop_orders(self) -> None:
        """Fill each line's stops, in travel order, from the GTFS trips."""
        self.client.download_gtfs(self.gtfs_path)
        for (code, sens), stops in stop_orders(self.gtfs_path, set(self.lines)).items():
            self.lines[code].stops[sens] = stops

    def _scheduled_departures(self, today: date) -> list[Departure]:
        """GTFS departures of the metro and funicular, for yesterday's and today's
        service. Yesterday's service runs past midnight (last metros at 24:xx)."""
        try:
            self.client.download_gtfs(self.gtfs_path)
        except requests.RequestException:
            if not self.gtfs_path.exists():
                raise
            # Grand Lyon is down: keep using the timetable we already have
        scheduled_lines = {
            line.code for line in self.lines.values() if line.mode in SCHEDULED_MODES
        }
        days = [today - timedelta(days=1), today]
        return build_departures(self.gtfs_path, days, scheduled_lines)

    def refresh_timetable(self, today: date) -> None:
        """Rebuild the scheduled departures when the day changes."""
        if self.scheduled_for != today:
            self.scheduled = self._scheduled_departures(today)
            self.scheduled_for = today

    def lines_of(self, mode: str) -> list[LineSummary]:
        """The lines of one tab, in natural order, without their stops."""
        return [
            LineSummary(
                code=line.code, colour=line.colour, destinations=line.destinations
            )
            for line in lines_of_mode(self.lines, mode)
        ]

    def _stops_of(self, code: str, sens: str) -> list[str]:
        """The platform ids of one direction of a line, in travel order."""
        if code not in self.lines or sens not in self.lines[code].stops:
            raise NotFound(f"unknown line {code} sens {sens}")
        return self.lines[code].stops[sens]

    def stops(self, code: str, sens: str) -> list[StopSummary]:
        """The stops of one direction of a line, in travel order."""
        return [
            StopSummary(platform=platform_id, name=self.platforms[platform_id].name)
            for platform_id in self._stops_of(code, sens)
        ]

    def line_map(self, code: str, sens: str) -> LineMap:
        """The trace of one direction of a line, and its stops in travel order."""
        stops = [
            MapStop(
                platform_id,
                self.platforms[platform_id].name,
                *self.positions[platform_id],
            )
            for platform_id in self._stops_of(code, sens)
            if platform_id in self.positions
        ]
        trace = self.traces.get((code, sens), [])
        return LineMap(colour=self.lines[code].colour, trace=trace, stops=stops)

    def departures(
        self, favourites: list[Favourite], now: datetime
    ) -> tuple[list[Departure], bool]:
        """GTFS departures plus real-time ones for these favourites, and if stale."""
        self.refresh_timetable(now.date())
        departures = list(self.scheduled)
        realtime_ids = [
            favourite.platform
            for favourite in favourites
            if self.lines[favourite.line].mode not in SCHEDULED_MODES
        ]

        stale = False
        if realtime_ids:
            stale = self.passages.refresh(
                lambda: self.client.fetch_passages(realtime_ids), now, realtime_ids
            )
        passages = latest_estimates(self.passages.rows)
        departures.extend(
            drop_doubled_schedules([parse_departure(passage) for passage in passages])
        )
        return departures, stale

    def current_alerts(self, now: datetime) -> tuple[list[Alert], bool]:
        """The active traffic alerts, and if they are stale."""
        stale = self.alerts.refresh(self.client.fetch_alerts, now)
        alerts = active_alerts([parse_alert(row) for row in self.alerts.rows], now)
        return alerts, stale

    def board(self, now: datetime) -> Board:
        """One card per favourite, with its next departures."""
        departures, passages_stale = self.departures(self.favourites, now)
        alerts, alerts_stale = self.current_alerts(now)
        cards = [
            build_card(favourite, self.platforms, self.lines, departures, alerts, now)
            for favourite in self.favourites
        ]
        return Board(
            cards=cards,
            banner=build_banner(self.favourites, alerts),
            now=now,
            # the passages are the fresher data; metro-only favourites have none
            updated_at=self.passages.fetched_at or self.alerts.fetched_at,
            stale=passages_stale or alerts_stale,
        )

    def stop_detail(
        self, platform: str, line: str, sens: str, now: datetime
    ) -> StopDetail:
        """The detail screen of one stop of a line: 6 departures and the next stops."""
        here = Favourite(line=line, sens=sens, platform=platform)
        errors = favourite_errors([here], self.platforms, self.lines)
        if errors:
            raise NotFound(errors)

        # ask for all favourites too, so the shared real-time cache keeps the board's
        departures, stale = self.departures([*self.favourites, here], now)
        at_platform = [d for d in departures if d.platform == platform]
        stops = self.lines[line].stops.get(sens, [])
        shown, remaining = timeline(stops, platform, self.platforms)
        return StopDetail(
            line=line,
            colour=self.lines[line].colour,
            platform_name=self.platforms[platform].name,
            destination=self.lines[line].destinations[sens],
            departures=next_departures(at_platform, line, now, n=6),
            next_stops=shown,
            remaining=remaining,
            favourite=here in self.favourites,
            now=now,
            stale=stale,
        )

    def alerts_page(self, now: datetime) -> AlertsPage:
        """Active alerts, most serious first: on the favourite lines, and network-wide."""
        alerts, stale = self.current_alerts(now)
        alerts.sort(key=lambda alert: (alert.severity, alert.line))
        favourite_lines = {favourite.line for favourite in self.favourites}
        return AlertsPage(
            mine=[alert for alert in alerts if alert.line in favourite_lines],
            network=alerts,
            updated_at=self.alerts.fetched_at,
            stale=stale,
        )

    def set_favourites(self, favourites: list[Favourite]) -> None:
        """Check, save and use these favourites; keep the old ones if invalid."""
        errors = favourite_errors(favourites, self.platforms, self.lines)
        if errors:
            raise InvalidFavourites(errors)
        save_favourites(self.fav_path, favourites)
        self.favourites = favourites
