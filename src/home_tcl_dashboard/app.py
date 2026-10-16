from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from home_tcl_dashboard.board import Board, Favourite
from home_tcl_dashboard.dashboard import (
    AlertsPage,
    Dashboard,
    InvalidFavourites,
    LineMap,
    LineSummary,
    NotFound,
    StopDetail,
    StopSummary,
)
from home_tcl_dashboard.grandlyon import GrandLyon

DATA_DIR = Path("data")
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.state.dashboard = Dashboard.load(GrandLyon.from_env(), DATA_DIR)
    yield


app = FastAPI(lifespan=lifespan)


def get_dashboard(request: Request) -> Dashboard:
    return request.app.state.dashboard


# A route parameter of this type receives the app's Dashboard
CurrentDashboard = Annotated[Dashboard, Depends(get_dashboard)]


@app.exception_handler(NotFound)
async def not_found(request: Request, error: NotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": error.args[0]})


@app.exception_handler(InvalidFavourites)
async def invalid_favourites(
    request: Request, error: InvalidFavourites
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": error.args[0]})


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
def get_favourites(dashboard: CurrentDashboard) -> list[Favourite]:
    return dashboard.favourites


@app.put("/api/favourites")
def put_favourites(
    favourites: list[Favourite], dashboard: CurrentDashboard
) -> list[Favourite]:
    dashboard.set_favourites(favourites)
    return favourites


@app.get("/api/lines")
def get_lines(
    mode: Literal["metro", "tram", "bus"], dashboard: CurrentDashboard
) -> list[LineSummary]:
    return dashboard.lines_of(mode)


@app.get("/api/lines/{code}/{sens}/stops")
def get_stops(
    code: str, sens: Literal["A", "R"], dashboard: CurrentDashboard
) -> list[StopSummary]:
    return dashboard.stops(code, sens)


@app.get("/api/lines/{code}/{sens}/map")
def get_line_map(
    code: str, sens: Literal["A", "R"], dashboard: CurrentDashboard
) -> LineMap:
    return dashboard.line_map(code, sens)


@app.get("/api/stops/{platform}/{line}/{sens}")
def stop_detail(
    platform: str, line: str, sens: Literal["A", "R"], dashboard: CurrentDashboard
) -> StopDetail:
    return dashboard.stop_detail(platform, line, sens, datetime.now())


@app.get("/api/alerts")
def get_alerts(dashboard: CurrentDashboard) -> AlertsPage:
    return dashboard.alerts_page(datetime.now())


@app.get("/api/board")
def board(dashboard: CurrentDashboard) -> Board:
    return dashboard.board(datetime.now())


app.mount(
    "/pictos",
    StaticFiles(directory=DATA_DIR / "pictos", check_dir=False),
    name="pictos",
)
# Last: a mount on "/" catches every URL, so the /api routes must come first.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
