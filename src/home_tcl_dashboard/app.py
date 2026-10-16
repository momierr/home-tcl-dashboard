from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import State

from home_tcl_dashboard.alerts import Alert, active_alerts, parse_alert
from home_tcl_dashboard.board import Board, Favourite, build_banner, build_card
from home_tcl_dashboard.cache import LastGood
from home_tcl_dashboard.favourites import (
    favourite_errors,
    load_favourites,
    save_favourites,
)
from home_tcl_dashboard.grandlyon import (
    download_gtfs,
    download_pictograms,
    fetch_alerts,
    fetch_passages,
    fetch_wfs,
    get_auth,
)
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


GTFS_PATH = Path("data/GTFS_TCL.ZIP")
STATIC_DIR = Path(__file__).parent / "static"
FAV_PATH = Path("data/favourites.json")
PICTOS_DIR = Path("data/pictos")


def load_network() -> tuple[dict[str, Platform], dict[str, Line]]:
    """Platforms by id and lines by code, from the WFS."""
    platform_rows = fetch_wfs("tclarret", "id,nom,desserte")
    platforms = {row["id"]: parse_platform(row) for row in platform_rows}

    line_rows: list[dict[str, str]] = []
    for layer in LINE_LAYERS:
        line_rows.extend(fetch_wfs(layer, LINE_PROPERTIES, REGULAR_TRACES))
    lines = parse_lines(line_rows)

    return platforms, lines


def load_scheduled_departures(lines: dict[str, Line], today: date) -> list[Departure]:
    """GTFS departures of the metro and funicular, for yesterday's and today's service.

    Yesterday's service runs past midnight (its last metros leave at 24:xx).
    """
    try:
        download_gtfs(GTFS_PATH, auth=get_auth())
    except requests.RequestException:
        if not GTFS_PATH.exists():
            raise
        # Grand Lyon is down: keep using the timetable we already have
    scheduled_lines = {
        line.code for line in lines.values() if line.mode in SCHEDULED_MODES
    }
    days = [today - timedelta(days=1), today]
    return build_departures(GTFS_PATH, days, scheduled_lines)


def refresh_timetable(state: State, today: date) -> None:
    """Rebuild the scheduled departures when the day changes."""
    if state.scheduled_for != today:
        state.scheduled = load_scheduled_departures(state.lines, today)
        state.scheduled_for = today


def load_stop_orders(lines: dict[str, Line]) -> None:
    """Fill each line's stops, in travel order, from the GTFS trips."""
    download_gtfs(GTFS_PATH, auth=get_auth())
    for (code, sens), stops in stop_orders(GTFS_PATH, set(lines)).items():
        lines[code].stops[sens] = stops


def load_geometry() -> tuple[
    dict[str, Point], dict[tuple[str, str], list[list[Point]]]
]:
    """Platform positions and line traces, for the line map (browse screen)."""
    positions = {
        row["id"]: parse_points(row["the_geom"])[0]
        for row in fetch_wfs("tclarret", "id,the_geom")
        if row["the_geom"]
    }
    line_rows = [
        row
        for layer in LINE_LAYERS
        for row in fetch_wfs(layer, "code_ligne,sens,the_geom", REGULAR_TRACES)
    ]
    return positions, parse_traces(line_rows)


def load_pictograms() -> None:
    """Download the line pictograms once; without them the screens show badges."""
    try:
        download_pictograms(PICTOS_DIR, get_auth())
    except requests.RequestException:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.state.platforms, app.state.lines = load_network()
    app.state.scheduled_for = None
    refresh_timetable(app.state, date.today())
    load_stop_orders(app.state.lines)
    load_pictograms()
    app.state.positions, app.state.traces = load_geometry()
    app.state.passages = LastGood(PASSAGES_MAX_AGE)
    app.state.alerts = LastGood(ALERTS_MAX_AGE)
    app.state.favourites = load_favourites(FAV_PATH)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/favourites")
def get_favourites(request: Request) -> list[Favourite]:
    return request.app.state.favourites


@app.put("/api/favourites")
def put_favourites(favourites: list[Favourite], request: Request) -> list[Favourite]:
    errors = favourite_errors(
        favourites, request.app.state.platforms, request.app.state.lines
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    save_favourites(FAV_PATH, favourites)
    request.app.state.favourites = favourites
    return favourites


@dataclass
class LineSummary:
    code: str
    colour: str
    destinations: dict[str, str]


@dataclass
class StopSummary:
    platform: str
    name: str


@app.get("/api/lines")
def get_lines(
    mode: Literal["metro", "tram", "bus"], request: Request
) -> list[LineSummary]:
    """The lines of one tab, in natural order, without their stops."""
    return [
        LineSummary(code=line.code, colour=line.colour, destinations=line.destinations)
        for line in lines_of_mode(request.app.state.lines, mode)
    ]


@app.get("/api/lines/{code}/{sens}/stops")
def get_stops(
    code: str, sens: Literal["A", "R"], request: Request
) -> list[StopSummary]:
    """The stops of one direction of a line, in travel order."""
    lines = request.app.state.lines
    if code not in lines or sens not in lines[code].stops:
        raise HTTPException(status_code=404, detail=f"unknown line {code} sens {sens}")
    platforms = request.app.state.platforms
    return [
        StopSummary(platform=platform_id, name=platforms[platform_id].name)
        for platform_id in lines[code].stops[sens]
    ]


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


@app.get("/api/lines/{code}/{sens}/map")
def get_line_map(code: str, sens: Literal["A", "R"], request: Request) -> LineMap:
    """The trace of one direction of a line, and its stops in travel order."""
    lines = request.app.state.lines
    if code not in lines or sens not in lines[code].stops:
        raise HTTPException(status_code=404, detail=f"unknown line {code} sens {sens}")
    platforms = request.app.state.platforms
    positions = request.app.state.positions
    stops = [
        MapStop(platform_id, platforms[platform_id].name, *positions[platform_id])
        for platform_id in lines[code].stops[sens]
        if platform_id in positions
    ]
    trace = request.app.state.traces.get((code, sens), [])
    return LineMap(colour=lines[code].colour, trace=trace, stops=stops)


def current_departures(
    request: Request, favourites: list[Favourite], now: datetime
) -> tuple[list[Departure], bool]:
    """GTFS departures plus real-time ones for these favourites, and if stale."""
    lines = request.app.state.lines
    refresh_timetable(request.app.state, now.date())
    departures = list(request.app.state.scheduled)
    realtime_ids = [
        favourite.platform
        for favourite in favourites
        if lines[favourite.line].mode not in SCHEDULED_MODES
    ]

    stale = False
    if realtime_ids:
        stale = request.app.state.passages.refresh(
            lambda: fetch_passages(realtime_ids, get_auth()), now, realtime_ids
        )
    passages = latest_estimates(request.app.state.passages.rows)
    departures.extend(
        drop_doubled_schedules([parse_departure(passage) for passage in passages])
    )
    return departures, stale


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


@app.get("/api/stops/{platform}/{line}/{sens}")
def stop_detail(
    platform: str, line: str, sens: Literal["A", "R"], request: Request
) -> StopDetail:
    """The detail screen of one stop of a line: 6 departures and the next stops."""
    platforms = request.app.state.platforms
    lines = request.app.state.lines
    here = Favourite(line=line, sens=sens, platform=platform)
    errors = favourite_errors([here], platforms, lines)
    if errors:
        raise HTTPException(status_code=404, detail=errors)

    now = datetime.now()
    favourites = request.app.state.favourites
    # ask for all favourites too, so the shared real-time cache keeps the board's
    departures, stale = current_departures(request, [*favourites, here], now)
    at_platform = [d for d in departures if d.platform == platform]
    shown, remaining = timeline(lines[line].stops.get(sens, []), platform, platforms)
    return StopDetail(
        line=line,
        colour=lines[line].colour,
        platform_name=platforms[platform].name,
        destination=lines[line].destinations[sens],
        departures=next_departures(at_platform, line, now, n=6),
        next_stops=shown,
        remaining=remaining,
        favourite=here in favourites,
        now=now,
        stale=stale,
    )


def current_alerts(request: Request, now: datetime) -> tuple[list[Alert], bool]:
    """The active traffic alerts, and if they are stale."""
    stale = request.app.state.alerts.refresh(lambda: fetch_alerts(get_auth()), now)
    alerts = active_alerts(
        [parse_alert(row) for row in request.app.state.alerts.rows], now
    )
    return alerts, stale


@dataclass
class AlertsPage:
    mine: list[Alert]
    network: list[Alert]
    updated_at: datetime | None
    stale: bool


@app.get("/api/alerts")
def get_alerts(request: Request) -> AlertsPage:
    """Active alerts, most serious first: on the favourite lines, and network-wide."""
    now = datetime.now()
    alerts, stale = current_alerts(request, now)
    alerts.sort(key=lambda alert: (alert.severity, alert.line))
    favourite_lines = {favourite.line for favourite in request.app.state.favourites}
    return AlertsPage(
        mine=[alert for alert in alerts if alert.line in favourite_lines],
        network=alerts,
        updated_at=request.app.state.alerts.fetched_at,
        stale=stale,
    )


@app.get("/api/board")
def board(request: Request) -> Board:
    """One card per favourite, with its next departures."""
    lines = request.app.state.lines
    now = datetime.now()
    departures, passages_stale = current_departures(
        request, request.app.state.favourites, now
    )
    alerts, alerts_stale = current_alerts(request, now)

    platforms = request.app.state.platforms
    cards = [
        build_card(favourite, platforms, lines, departures, alerts, now)
        for favourite in request.app.state.favourites
    ]
    return Board(
        cards=cards,
        banner=build_banner(request.app.state.favourites, alerts),
        now=now,
        # the passages are the fresher data; metro-only favourites have none
        updated_at=request.app.state.passages.fetched_at
        or request.app.state.alerts.fetched_at,
        stale=passages_stale or alerts_stale,
    )


app.mount("/pictos", StaticFiles(directory=PICTOS_DIR, check_dir=False), name="pictos")
# Last: a mount on "/" catches every URL, so the /api routes must come first.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
