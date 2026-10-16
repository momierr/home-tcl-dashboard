from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request

from home_tcl_dashboard.alerts import active_alerts, parse_alert
from home_tcl_dashboard.board import Board, Favourite, build_banner, build_card
from home_tcl_dashboard.cache import LastGood
from home_tcl_dashboard.favourites import (
    favourite_errors,
    load_favourites,
    save_favourites,
)
from home_tcl_dashboard.grandlyon import (
    download_gtfs,
    fetch_alerts,
    fetch_passages,
    fetch_wfs,
    get_auth,
)
from home_tcl_dashboard.gtfs import build_departures, stop_orders
from home_tcl_dashboard.network import (
    Line,
    Platform,
    lines_of_mode,
    parse_lines,
    parse_platform,
)
from home_tcl_dashboard.realtime import Departure, latest_estimates, parse_departure

LINE_LAYERS = ["tcllignemf_2_0_0", "tcllignetram_2_0_0", "tcllignebus_2_0_0"]
LINE_PROPERTIES = "code_ligne,sens,nom_destination,famille_transport,couleur_hex"
REGULAR_TRACES = "type_trace='NOM' AND code_type_ligne='REG'"
SCHEDULED_MODES = {"MET", "FUN"}


GTFS_PATH = Path("data/GTFS_TCL.ZIP")
FAV_PATH = Path("data/favourites.json")


def load_network() -> tuple[dict[str, Platform], dict[str, Line]]:
    """Platforms by id and lines by code, from the WFS."""
    platform_rows = fetch_wfs("tclarret", "id,nom,desserte")
    platforms = {row["id"]: parse_platform(row) for row in platform_rows}

    line_rows: list[dict[str, str]] = []
    for layer in LINE_LAYERS:
        line_rows.extend(fetch_wfs(layer, LINE_PROPERTIES, REGULAR_TRACES))
    lines = parse_lines(line_rows)

    return platforms, lines


def load_scheduled_departures(lines: dict[str, Line]) -> list[Departure]:
    download_gtfs(GTFS_PATH, auth=get_auth())
    scheduled_lines = {
        line.code for line in lines.values() if line.mode in SCHEDULED_MODES
    }
    return build_departures(GTFS_PATH, date.today(), scheduled_lines)


def load_stop_orders(lines: dict[str, Line]) -> None:
    """Fill each line's stops, in travel order, from the GTFS trips."""
    download_gtfs(GTFS_PATH, auth=get_auth())
    for (code, sens), stops in stop_orders(GTFS_PATH, set(lines)).items():
        lines[code].stops[sens] = stops


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.state.platforms, app.state.lines = load_network()
    app.state.scheduled = load_scheduled_departures(app.state.lines)
    load_stop_orders(app.state.lines)
    app.state.passages = LastGood()
    app.state.alerts = LastGood()
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


@app.get("/api/lines")
def get_lines(
    mode: Literal["metro", "tram", "bus"], request: Request
) -> list[LineSummary]:
    """The lines of one tab, in natural order, without their stops."""
    return [
        LineSummary(code=line.code, colour=line.colour, destinations=line.destinations)
        for line in lines_of_mode(request.app.state.lines, mode)
    ]


@app.get("/api/board")
def board(request: Request) -> Board:
    """One card per favourite, with its next departures."""
    lines = request.app.state.lines
    departures = list(request.app.state.scheduled)
    realtime_ids = [
        favourite.platform
        for favourite in request.app.state.favourites
        if lines[favourite.line].mode not in SCHEDULED_MODES
    ]

    now = datetime.now()

    passages_stale = False

    if realtime_ids:
        passages_stale = request.app.state.passages.refresh(
            lambda: fetch_passages(realtime_ids, get_auth()), now
        )
    passages = latest_estimates(request.app.state.passages.rows)

    departures.extend(parse_departure(passage) for passage in passages)

    alerts_stale = request.app.state.alerts.refresh(
        lambda: fetch_alerts(get_auth()), now
    )
    alerts = active_alerts(
        [parse_alert(row) for row in request.app.state.alerts.rows], now
    )

    platforms = request.app.state.platforms
    cards = [
        build_card(favourite, platforms, lines, departures, alerts, now)
        for favourite in request.app.state.favourites
    ]
    return Board(
        cards=cards,
        banner=build_banner(request.app.state.favourites, alerts),
        now=now,
        updated_at=request.app.state.alerts.fetched_at,
        stale=passages_stale or alerts_stale,
    )
