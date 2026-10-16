"""End-to-end tests of the HTTP layer: routes, status codes, JSON, headers.
What the screens show is tested on Dashboard itself, in test_dashboard.py."""

from datetime import datetime
from pathlib import Path

import pytest
from fakes import FAKE_LINES, FakeGrandLyon, make_dashboard
from fastapi.testclient import TestClient

from home_tcl_dashboard import app as app_module
from home_tcl_dashboard.app import app
from home_tcl_dashboard.board import Favourite
from home_tcl_dashboard.network import Line

FAVOURITE = {"line": "T2", "sens": "A", "platform": "32103"}
T2_WITH_STOPS = {
    **FAKE_LINES,
    "T2": Line(
        "T2",
        "TRA",
        "#6BA230",
        {"A": "Saint-Priest Bel Air"},
        stops={"A": ["32103", "33685"]},
    ),
}


@pytest.fixture
def http(monkeypatch, tmp_path):
    """A client of the app, started on a hand-made Dashboard: no network."""
    client = FakeGrandLyon()
    dashboard = make_dashboard(tmp_path, lines=T2_WITH_STOPS, client=client)
    dashboard.scheduled_for = datetime.now().date()  # no GTFS file to read
    loaded_with = []

    def load(grand_lyon, data_dir):
        loaded_with.append((grand_lyon, data_dir))
        return dashboard

    monkeypatch.setattr(app_module.GrandLyon, "from_env", lambda: client)
    monkeypatch.setattr(app_module.Dashboard, "load", load)
    with TestClient(app) as test_client:
        test_client.dashboard = dashboard
        test_client.loaded_with = loaded_with
        yield test_client


def test_startup_loads_the_dashboard_from_the_env_into_data(http):
    assert http.loaded_with == [(http.dashboard.client, app_module.DATA_DIR)]


def test_health_returns_ok(http):
    response = http.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_the_home_page_is_served_and_revalidated(http):
    page = http.get("/")
    api = http.get("/api/health")

    assert page.status_code == 200
    assert "app.js" in page.text
    assert page.headers["cache-control"] == "no-cache"
    assert "cache-control" not in api.headers


def test_favourites_are_empty_then_saved(http):
    assert http.get("/api/favourites").json() == []

    response = http.put("/api/favourites", json=[FAVOURITE])

    assert response.status_code == 200
    assert http.get("/api/favourites").json() == [FAVOURITE]
    assert http.dashboard.favourites == [Favourite(**FAVOURITE)]


def test_invalid_favourites_are_refused_with_their_errors(http):
    response = http.put(
        "/api/favourites", json=[{"line": "ZZZ", "sens": "A", "platform": "32103"}]
    )

    assert response.status_code == 422
    assert response.json() == {"detail": ["unknown line ZZZ"]}
    assert http.get("/api/favourites").json() == []


def test_lines_of_a_tab(http):
    response = http.get("/api/lines?mode=tram")

    assert response.json() == [
        {
            "code": "T2",
            "colour": "#6BA230",
            "destinations": {"A": "Saint-Priest Bel Air"},
        }
    ]


@pytest.mark.parametrize(
    "url, status",
    [
        ("/api/lines?mode=boat", 422),  # not a tab
        ("/api/lines/T2/A/stops", 200),
        ("/api/lines/ZZZ/A/stops", 404),  # unknown line: NotFound
        ("/api/lines/T2/R/stops", 404),  # no stops that way: NotFound
        ("/api/lines/T2/X/stops", 422),  # not a sens at all: FastAPI
        ("/api/lines/T2/A/map", 200),
        ("/api/lines/ZZZ/A/map", 404),
        ("/api/stops/32103/T2/A", 200),
        ("/api/stops/32103/T2/R", 404),
    ],
)
def test_status_codes(http, url, status):
    assert http.get(url).status_code == status


def test_an_unknown_stop_says_why(http):
    response = http.get("/api/stops/32103/T2/R")

    assert response.json() == {"detail": ["line T2 sens R does not stop at 32103"]}


def test_the_stops_of_a_direction(http):
    assert http.get("/api/lines/T2/A/stops").json() == [
        {"platform": "32103", "name": "Perrache"},
        {"platform": "33685", "name": "Bellecour A. Poncet"},
    ]


def test_the_board_as_json(http):
    http.dashboard.client.passages = lambda platform_ids: [
        {
            "id": "32103",
            "ligne": "T2",
            "heurepassage": "2099-01-01 08:05:00",
            "type": "E",
            "coursetheorique": "trip-t2",
            "last_update_fme": "2099-01-01 08:00:00",
        }
    ]
    http.put("/api/favourites", json=[FAVOURITE])

    body = http.get("/api/board").json()

    assert body.pop("now")
    assert body.pop("updated_at")
    assert body == {
        "cards": [
            {
                "line": "T2",
                "sens": "A",
                "platform": "32103",
                "colour": "#6BA230",
                "platform_name": "Perrache",
                "destination": "Saint-Priest Bel Air",
                "departures": [
                    {
                        "line": "T2",
                        "platform": "32103",
                        "time": "2099-01-01T08:05:00",
                        "realtime": True,
                    }
                ],
                "disrupted": False,
            }
        ],
        "banner": None,
        "stale": False,
    }


def test_the_alerts_page_as_json(http):
    body = http.get("/api/alerts").json()

    assert body.pop("updated_at")
    assert body == {"mine": [], "network": [], "stale": False}


def test_data_dir_is_data_by_default(monkeypatch):
    monkeypatch.delenv("TCL_DATA_DIR", raising=False)

    assert app_module.data_dir() == Path("data")


def test_data_dir_can_be_set_by_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("TCL_DATA_DIR", str(tmp_path))

    assert app_module.data_dir() == tmp_path
