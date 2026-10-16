from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

import requests
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import State

from home_tcl_dashboard.alerts import Alert, active_alerts, parse_alert
from home_tcl_dashboard.board import Board, Favourite, build_banner, build_card
from home_tcl_dashboard.cache import LastGood
from home_tcl_dashboard.dashboard import (
    ALERTS_MAX_AGE,
    PASSAGES_MAX_AGE,
    SCHEDULED_MODES,
    AlertsPage,
    LineMap,
    LineSummary,
    MapStop,
    StopDetail,
    StopSummary,
    load_geometry,
    load_network,
    load_pictograms,
)
from home_tcl_dashboard.favourites import (
    favourite_errors,
    load_favourites,
    save_favourites,
)
from home_tcl_dashboard.grandlyon import GrandLyon
from home_tcl_dashboard.gtfs import build_departures, stop_orders
from home_tcl_dashboard.network import (
    Line,
    lines_of_mode,
    timeline,
)
from home_tcl_dashboard.realtime import (
    Departure,
    drop_doubled_schedules,
    latest_estimates,
    next_departures,
    parse_departure,
)

GTFS_PATH = Path("data/GTFS_TCL.ZIP")
STATIC_DIR = Path(__file__).parent / "static"
FAV_PATH = Path("data/favourites.json")
PICTOS_DIR = Path("data/pictos")


def load_scheduled_departures(
    client: GrandLyon, lines: dict[str, Line], today: date
) -> list[Departure]:
    """GTFS departures of the metro and funicular, for yesterday's and today's service.

    Yesterday's service runs past midnight (its last metros leave at 24:xx).
    """
    try:
        client.download_gtfs(GTFS_PATH)
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
        state.scheduled = load_scheduled_departures(state.grandlyon, state.lines, today)
        state.scheduled_for = today


def load_stop_orders(client: GrandLyon, lines: dict[str, Line]) -> None:
    """Fill each line's stops, in travel order, from the GTFS trips."""
    client.download_gtfs(GTFS_PATH)
    for (code, sens), stops in stop_orders(GTFS_PATH, set(lines)).items():
        lines[code].stops[sens] = stops


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    client = GrandLyon.from_env()
    app.state.grandlyon = client
    app.state.platforms, app.state.lines = load_network(client)
    app.state.scheduled_for = None
    refresh_timetable(app.state, date.today())
    load_stop_orders(client, app.state.lines)
    load_pictograms(client, PICTOS_DIR)
    app.state.positions, app.state.traces = load_geometry(client)
    app.state.passages = LastGood(PASSAGES_MAX_AGE)
    app.state.alerts = LastGood(ALERTS_MAX_AGE)
    app.state.favourites = load_favourites(FAV_PATH)
    yield


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def revalidate_files(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Without a Cache-Control header, browsers guess how long to keep a file, and
    the tablet could run an old app.js after an update. "no-cache" makes them ask
    each time; the ETag answers "not modified" cheaply when nothing changed."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


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
            lambda: request.app.state.grandlyon.fetch_passages(realtime_ids),
            now,
            realtime_ids,
        )
    passages = latest_estimates(request.app.state.passages.rows)
    departures.extend(
        drop_doubled_schedules([parse_departure(passage) for passage in passages])
    )
    return departures, stale


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
    stale = request.app.state.alerts.refresh(
        lambda: request.app.state.grandlyon.fetch_alerts(), now
    )
    alerts = active_alerts(
        [parse_alert(row) for row in request.app.state.alerts.rows], now
    )
    return alerts, stale


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
