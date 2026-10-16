from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request

from home_tcl_dashboard.board import Card, Favourite, build_card
from home_tcl_dashboard.grandlyon import fetch_passages, fetch_wfs, get_auth
from home_tcl_dashboard.network import Line, Platform, parse_lines, parse_platform
from home_tcl_dashboard.realtime import latest_estimates, parse_departure

LINE_LAYERS = ["tcllignemf_2_0_0", "tcllignetram_2_0_0", "tcllignebus_2_0_0"]
LINE_PROPERTIES = "code_ligne,sens,nom_destination,famille_transport,couleur_hex"
REGULAR_TRACES = "type_trace='NOM' AND code_type_ligne='REG'"

FAVOURITES = [
    Favourite(line="T2", sens="A", platform="32103"),  # Perrache
    Favourite(line="C9", sens="A", platform="33685"),  # Bellecour A. Poncet
]


def load_network() -> tuple[dict[str, Platform], dict[str, Line]]:
    """Platforms by id and lines by code, from the WFS."""
    platform_rows = fetch_wfs("tclarret", "id,nom,desserte")
    platforms = {row["id"]: parse_platform(row) for row in platform_rows}

    line_rows: list[dict[str, str]] = []
    for layer in LINE_LAYERS:
        line_rows.extend(fetch_wfs(layer, LINE_PROPERTIES, REGULAR_TRACES))
    lines = parse_lines(line_rows)

    return platforms, lines


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.state.platforms, app.state.lines = load_network()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/board")
def board(request: Request) -> list[Card]:
    """One card per favourite, with its next departures."""
    platform_ids = [favourite.platform for favourite in FAVOURITES]
    passages = latest_estimates(fetch_passages(platform_ids, get_auth()))
    departures = [parse_departure(passage) for passage in passages]
    platforms = request.app.state.platforms
    lines = request.app.state.lines
    now = datetime.now()
    return [
        build_card(favourite, platforms, lines, departures, now)
        for favourite in FAVOURITES
    ]
