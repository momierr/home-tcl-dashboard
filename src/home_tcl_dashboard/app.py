from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, Request

from home_tcl_dashboard.alerts import active_alerts, parse_alert
from home_tcl_dashboard.board import Board, Favourite, build_banner, build_card
from home_tcl_dashboard.grandlyon import (
    download_gtfs,
    fetch_alerts,
    fetch_passages,
    fetch_wfs,
    get_auth,
)
from home_tcl_dashboard.gtfs import build_departures
from home_tcl_dashboard.network import Line, Platform, parse_lines, parse_platform
from home_tcl_dashboard.realtime import Departure, latest_estimates, parse_departure

LINE_LAYERS = ["tcllignemf_2_0_0", "tcllignetram_2_0_0", "tcllignebus_2_0_0"]
LINE_PROPERTIES = "code_ligne,sens,nom_destination,famille_transport,couleur_hex"
REGULAR_TRACES = "type_trace='NOM' AND code_type_ligne='REG'"
SCHEDULED_MODES = {"MET", "FUN"}

FAVOURITES = [
    Favourite(line="T2", sens="A", platform="32103"),  # Perrache
    Favourite(line="C9", sens="A", platform="33685"),  # Bellecour A. Poncet
]

GTFS_PATH = Path("data/GTFS_TCL.ZIP")


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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.state.platforms, app.state.lines = load_network()
    app.state.scheduled = load_scheduled_departures(app.state.lines)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/board")
def board(request: Request) -> Board:
    """One card per favourite, with its next departures."""
    lines = request.app.state.lines
    departures = list(request.app.state.scheduled)
    realtime_ids = [
        favourite.platform
        for favourite in FAVOURITES
        if lines[favourite.line].mode not in SCHEDULED_MODES
    ]

    if realtime_ids:
        passages = latest_estimates(fetch_passages(realtime_ids, get_auth()))
        departures.extend(parse_departure(passage) for passage in passages)

    now = datetime.now()
    alerts = active_alerts([parse_alert(row) for row in fetch_alerts(get_auth())], now)
    platforms = request.app.state.platforms
    cards = [
        build_card(favourite, platforms, lines, departures, alerts, now)
        for favourite in FAVOURITES
    ]
    return Board(cards=cards, banner=build_banner(FAVOURITES, alerts))
