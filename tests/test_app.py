from datetime import date, datetime, timedelta

import pytest
import requests
from fastapi.testclient import TestClient
from starlette.datastructures import State

from home_tcl_dashboard import app as app_module
from home_tcl_dashboard.app import app
from home_tcl_dashboard.board import Favourite
from home_tcl_dashboard.favourites import load_favourites, save_favourites
from home_tcl_dashboard.network import Line, Platform
from home_tcl_dashboard.realtime import Departure

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/api/health")
    assert response.json() == {"status": "ok"}
    assert response.status_code == 200


PLATFORM_ROWS = [{"id": "32103", "nom": "Perrache", "desserte": "T1:A,T2:A"}]
LINE_ROWS = {
    "tcllignemf_2_0_0": [],
    "tcllignetram_2_0_0": [
        {
            "code_ligne": "T2",
            "sens": "Aller",
            "nom_destination": "Saint-Priest Bel Air",
            "famille_transport": "TRA",
            "couleur_hex": "#6BA230",
        }
    ],
    "tcllignebus_2_0_0": [
        {
            "code_ligne": "C9",
            "sens": "Aller",
            "nom_destination": "Hopitaux Est",
            "famille_transport": "BUS",
            "couleur_hex": "#C88817",
        }
    ],
}


def fake_fetch_wfs(layer, properties, cql_filter=None):
    if layer == "tclarret":
        return PLATFORM_ROWS
    assert cql_filter == app_module.REGULAR_TRACES
    return LINE_ROWS[layer]


def test_load_network_indexes_platforms_and_lines(monkeypatch):
    monkeypatch.setattr(app_module, "fetch_wfs", fake_fetch_wfs)

    platforms, lines = app_module.load_network()

    assert platforms == {
        "32103": Platform(
            id="32103", name="Perrache", line_directions={("T1", "A"), ("T2", "A")}
        )
    }
    assert lines == {
        "T2": Line("T2", "TRA", "#6BA230", {"A": "Saint-Priest Bel Air"}),
        "C9": Line("C9", "BUS", "#C88817", {"A": "Hopitaux Est"}),
    }


FAKE_PLATFORMS = {
    "32103": Platform(
        id="32103", name="Perrache", line_directions={("T1", "A"), ("T2", "A")}
    ),
    "33685": Platform(
        id="33685", name="Bellecour A. Poncet", line_directions={("C9", "A")}
    ),
}

FAKE_LINES = {
    "T2": Line("T2", "TRA", "#6BA230", {"A": "Saint-Priest Bel Air"}),
    "C9": Line("C9", "BUS", "#C88817", {"A": "Hopitaux Est"}),
}

FAKE_FAVOURITES = [
    Favourite(line="T2", sens="A", platform="32103"),
    Favourite(line="C9", sens="A", platform="33685"),
]
FAKE_PASSAGES = [
    {
        "id": "32103",
        "ligne": "T2",
        "heurepassage": "2099-01-01 08:05:00",
        "type": "E",
        "coursetheorique": "trip-t2",
        "last_update_fme": "2099-01-01 08:00:00",
    },
    {
        "id": "33685",
        "ligne": "C9",
        "heurepassage": "2099-01-01 08:10:00",
        "type": "T",
        "coursetheorique": "trip-c9",
        "last_update_fme": "2099-01-01 08:00:00",
    },
]


def test_board_returns_one_card_per_favourite(monkeypatch):
    requested_ids = []

    def fake_fetch_passages(platform_ids, auth):
        requested_ids.extend(platform_ids)
        return FAKE_PASSAGES

    monkeypatch.setattr(
        app_module, "load_network", lambda: (FAKE_PLATFORMS, FAKE_LINES)
    )
    monkeypatch.setattr(
        app_module, "load_scheduled_departures", lambda lines, today: []
    )
    monkeypatch.setattr(app_module, "load_stop_orders", lambda lines: None)
    monkeypatch.setattr(app_module, "load_pictograms", lambda: None)
    monkeypatch.setattr(app_module, "load_geometry", lambda: ({}, {}))
    monkeypatch.setattr(app_module, "load_favourites", lambda path: FAKE_FAVOURITES)
    monkeypatch.setattr(app_module, "get_auth", lambda: ("user", "pwd"))
    monkeypatch.setattr(app_module, "fetch_passages", fake_fetch_passages)
    monkeypatch.setattr(app_module, "fetch_alerts", lambda auth: [])

    with TestClient(app) as client:
        response = client.get("/api/board")

    assert response.status_code == 200
    body = response.json()
    assert body.pop("stale") is False
    assert body.pop("updated_at") == body.pop("now")  # fresh: fetched right now
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
            },
            {
                "line": "C9",
                "sens": "A",
                "platform": "33685",
                "colour": "#C88817",
                "platform_name": "Bellecour A. Poncet",
                "destination": "Hopitaux Est",
                "departures": [
                    {
                        "line": "C9",
                        "platform": "33685",
                        "time": "2099-01-01T08:10:00",
                        "realtime": False,
                    }
                ],
                "disrupted": False,
            },
        ],
        "banner": None,
    }
    assert requested_ids == ["32103", "33685"]


def test_board_uses_the_timetable_for_the_metro(monkeypatch):
    platforms = {
        "30101": Platform(id="30101", name="Perrache", line_directions={("A", "A")})
    }
    lines = {"A": Line("A", "MET", "#E8308A", {"A": "Vaulx-en-Velin La Soie"})}
    scheduled = Departure("A", "30101", datetime(2099, 1, 1, 8, 5), realtime=False)

    def no_realtime(platform_ids, auth):
        raise AssertionError("the metro must not ask for real-time data")

    monkeypatch.setattr(
        app_module,
        "load_favourites",
        lambda path: [Favourite(line="A", sens="A", platform="30101")],
    )
    monkeypatch.setattr(app_module, "load_network", lambda: (platforms, lines))
    monkeypatch.setattr(
        app_module, "load_scheduled_departures", lambda lines, today: [scheduled]
    )
    monkeypatch.setattr(app_module, "load_stop_orders", lambda lines: None)
    monkeypatch.setattr(app_module, "load_pictograms", lambda: None)
    monkeypatch.setattr(app_module, "load_geometry", lambda: ({}, {}))
    monkeypatch.setattr(app_module, "fetch_passages", no_realtime)
    monkeypatch.setattr(app_module, "get_auth", lambda: ("user", "pwd"))
    monkeypatch.setattr(app_module, "fetch_alerts", lambda auth: [])

    with TestClient(app) as client:
        response = client.get("/api/board")

    assert response.status_code == 200
    assert response.json()["cards"][0]["departures"] == [
        {
            "line": "A",
            "platform": "30101",
            "time": "2099-01-01T08:05:00",
            "realtime": False,
        }
    ]


def test_board_serves_stale_data_when_grand_lyon_is_down(monkeypatch):
    calls = []

    def flaky_fetch_passages(platform_ids, auth):
        calls.append(platform_ids)
        if len(calls) > 1:
            raise requests.ConnectionError()
        return FAKE_PASSAGES

    def down(auth):
        raise requests.ConnectionError()

    monkeypatch.setattr(
        app_module, "load_network", lambda: (FAKE_PLATFORMS, FAKE_LINES)
    )
    monkeypatch.setattr(
        app_module, "load_scheduled_departures", lambda lines, today: []
    )
    monkeypatch.setattr(app_module, "load_stop_orders", lambda lines: None)
    monkeypatch.setattr(app_module, "load_pictograms", lambda: None)
    monkeypatch.setattr(app_module, "load_geometry", lambda: ({}, {}))
    monkeypatch.setattr(app_module, "load_favourites", lambda path: FAKE_FAVOURITES)
    monkeypatch.setattr(app_module, "get_auth", lambda: ("user", "pwd"))
    monkeypatch.setattr(app_module, "fetch_passages", flaky_fetch_passages)
    monkeypatch.setattr(app_module, "fetch_alerts", down)
    # never reuse the passages: the second board must ask Grand Lyon again
    monkeypatch.setattr(app_module, "PASSAGES_MAX_AGE", timedelta(0))

    with TestClient(app) as client:
        first = client.get("/api/board")  # Grand Lyon answers: passages are cached
        response = client.get("/api/board")  # Grand Lyon is down

    assert response.status_code == 200
    body = response.json()
    assert body["stale"] is True
    assert body["updated_at"] == first.json()["now"]  # the last good passages
    assert [len(card["departures"]) for card in body["cards"]] == [1, 1]


def start_without_network(monkeypatch, favourites_path):
    monkeypatch.setattr(
        app_module, "load_network", lambda: (FAKE_PLATFORMS, FAKE_LINES)
    )
    monkeypatch.setattr(
        app_module, "load_scheduled_departures", lambda lines, today: []
    )
    monkeypatch.setattr(app_module, "load_stop_orders", lambda lines: None)
    monkeypatch.setattr(app_module, "load_pictograms", lambda: None)
    monkeypatch.setattr(app_module, "load_geometry", lambda: ({}, {}))
    monkeypatch.setattr(app_module, "FAV_PATH", favourites_path)


def test_get_favourites_is_empty_on_first_start(monkeypatch, tmp_path):
    start_without_network(monkeypatch, tmp_path / "favourites.json")

    with TestClient(app) as client:
        response = client.get("/api/favourites")

    assert response.status_code == 200
    assert response.json() == []


def test_put_favourites_saves_them_and_serves_them(monkeypatch, tmp_path):
    path = tmp_path / "favourites.json"
    start_without_network(monkeypatch, path)
    new = [
        {"line": "C9", "sens": "A", "platform": "33685"},
        {"line": "T2", "sens": "A", "platform": "32103"},
    ]

    with TestClient(app) as client:
        put = client.put("/api/favourites", json=new)
        get = client.get("/api/favourites")

    assert put.status_code == 200
    assert get.json() == new
    assert load_favourites(path) == [
        Favourite(line="C9", sens="A", platform="33685"),
        Favourite(line="T2", sens="A", platform="32103"),
    ]


def test_put_favourites_refuses_invalid_ones_and_keeps_the_old(monkeypatch, tmp_path):
    path = tmp_path / "favourites.json"
    start_without_network(monkeypatch, path)
    old = [{"line": "T2", "sens": "A", "platform": "32103"}]
    invalid = [{"line": "ZZZ", "sens": "A", "platform": "32103"}]

    with TestClient(app) as client:
        client.put("/api/favourites", json=old)
        put = client.put("/api/favourites", json=invalid)
        get = client.get("/api/favourites")

    assert put.status_code == 422
    assert put.json() == {"detail": ["unknown line ZZZ"]}
    assert get.json() == old
    assert load_favourites(path) == [Favourite(line="T2", sens="A", platform="32103")]


def test_get_lines_lists_one_tab_without_stops(monkeypatch, tmp_path):
    lines = {
        "T2": Line("T2", "TRA", "#6BA230", {"A": "Saint-Priest"}, stops={"A": ["1"]}),
        "C9": Line("C9", "BUS", "#C88817", {"A": "Hopitaux Est"}, stops={"A": ["2"]}),
    }
    start_without_network(monkeypatch, tmp_path / "favourites.json")
    monkeypatch.setattr(app_module, "load_network", lambda: (FAKE_PLATFORMS, lines))

    with TestClient(app) as client:
        response = client.get("/api/lines", params={"mode": "tram"})

    assert response.status_code == 200
    assert response.json() == [
        {"code": "T2", "colour": "#6BA230", "destinations": {"A": "Saint-Priest"}}
    ]


def test_get_lines_refuses_an_unknown_mode(monkeypatch, tmp_path):
    start_without_network(monkeypatch, tmp_path / "favourites.json")

    with TestClient(app) as client:
        response = client.get("/api/lines", params={"mode": "plane"})

    assert response.status_code == 422


def test_get_stops_lists_a_direction_in_travel_order(monkeypatch, tmp_path):
    lines = {
        "T2": Line("T2", "TRA", "#6BA230", stops={"A": ["33685", "32103"]}),
    }
    start_without_network(monkeypatch, tmp_path / "favourites.json")
    monkeypatch.setattr(app_module, "load_network", lambda: (FAKE_PLATFORMS, lines))

    with TestClient(app) as client:
        response = client.get("/api/lines/T2/A/stops")

    assert response.status_code == 200
    assert response.json() == [
        {"platform": "33685", "name": "Bellecour A. Poncet"},
        {"platform": "32103", "name": "Perrache"},
    ]


@pytest.mark.parametrize(
    "url, status",
    [
        ("/api/lines/ZZZ/A/stops", 404),  # unknown line
        ("/api/lines/T2/R/stops", 404),  # one-way line: no stops that way
        ("/api/lines/T2/X/stops", 422),  # not a sens at all
    ],
)
def test_get_stops_refuses_unknown_directions(monkeypatch, tmp_path, url, status):
    lines = {"T2": Line("T2", "TRA", "#6BA230", stops={"A": ["32103"]})}
    start_without_network(monkeypatch, tmp_path / "favourites.json")
    monkeypatch.setattr(app_module, "load_network", lambda: (FAKE_PLATFORMS, lines))

    with TestClient(app) as client:
        response = client.get(url)

    assert response.status_code == status


def test_stop_detail_shows_departures_and_next_stops(monkeypatch, tmp_path):
    lines = {
        "T2": Line(
            "T2",
            "TRA",
            "#6BA230",
            {"A": "Saint-Priest Bel Air"},
            stops={"A": ["32103", "33685"]},
        ),
        "C9": FAKE_LINES["C9"],
    }
    requested_ids = []

    def fake_fetch_passages(platform_ids, auth):
        requested_ids.extend(platform_ids)
        return FAKE_PASSAGES

    path = tmp_path / "favourites.json"
    save_favourites(path, [Favourite(line="C9", sens="A", platform="33685")])
    start_without_network(monkeypatch, path)
    monkeypatch.setattr(app_module, "load_network", lambda: (FAKE_PLATFORMS, lines))
    monkeypatch.setattr(app_module, "get_auth", lambda: ("user", "pwd"))
    monkeypatch.setattr(app_module, "fetch_passages", fake_fetch_passages)

    with TestClient(app) as client:
        response = client.get("/api/stops/32103/T2/A")

    assert response.status_code == 200
    body = response.json()
    assert body.pop("now")
    assert body == {
        "line": "T2",
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
        "next_stops": ["Perrache", "Bellecour A. Poncet"],
        "remaining": 0,
        "favourite": False,
        "stale": False,
    }
    # the board's favourite platform is fetched too, to keep the shared cache
    assert requested_ids == ["33685", "32103"]


def test_stop_detail_refuses_an_unknown_stop(monkeypatch, tmp_path):
    start_without_network(monkeypatch, tmp_path / "favourites.json")

    with TestClient(app) as client:
        response = client.get("/api/stops/32103/T2/R")

    assert response.status_code == 404


def test_refresh_timetable_rebuilds_once_a_day(monkeypatch):
    built_for = []

    def fake_load(lines, today):
        built_for.append(today)
        return []

    monkeypatch.setattr(app_module, "load_scheduled_departures", fake_load)
    state = State({"lines": {}, "scheduled_for": None})

    app_module.refresh_timetable(state, date(2026, 10, 16))
    app_module.refresh_timetable(state, date(2026, 10, 16))
    app_module.refresh_timetable(state, date(2026, 10, 17))

    assert built_for == [date(2026, 10, 16), date(2026, 10, 17)]


def test_load_scheduled_departures_keeps_the_old_file_when_download_fails(
    monkeypatch, tmp_path
):
    path = tmp_path / "gtfs.zip"
    path.write_bytes(b"yesterday's timetable")
    built_from = []

    def down(path, auth):
        raise requests.ConnectionError()

    def fake_build(path, days, lines):
        built_from.append((path, days))
        return []

    monkeypatch.setattr(app_module, "GTFS_PATH", path)
    monkeypatch.setattr(app_module, "get_auth", lambda: ("user", "pwd"))
    monkeypatch.setattr(app_module, "download_gtfs", down)
    monkeypatch.setattr(app_module, "build_departures", fake_build)

    app_module.load_scheduled_departures({}, date(2026, 10, 16))

    assert built_from == [(path, [date(2026, 10, 15), date(2026, 10, 16)])]


def test_the_home_page_is_served(monkeypatch, tmp_path):
    start_without_network(monkeypatch, tmp_path / "favourites.json")

    with TestClient(app) as client:
        page = client.get("/")
        api = client.get("/api/health")

    assert page.status_code == 200
    assert "app.js" in page.text
    assert api.json() == {"status": "ok"}


def test_get_alerts_splits_my_lines_from_the_network(monkeypatch, tmp_path):
    path = tmp_path / "favourites.json"
    save_favourites(path, [Favourite(line="T2", sens="A", platform="32103")])
    start_without_network(monkeypatch, path)
    monkeypatch.setattr(app_module, "get_auth", lambda: ("user", "pwd"))
    rows = [
        {
            "ligne_cli": line,
            "type": "Perturbation",
            "niveauseverite": severity,
            "debut": "2026-01-01 00:00:00",
            "fin": "2099-01-01 00:00:00",
            "titre": title,
            "message": "",
        }
        for line, severity, title in [
            ("C9", 30, "Info C9"),
            ("T2", 30, "Info T2"),
            ("T2", 20, "Travaux T2"),
        ]
    ]
    monkeypatch.setattr(app_module, "fetch_alerts", lambda auth: rows)

    with TestClient(app) as client:
        body = client.get("/api/alerts").json()

    assert [alert["title"] for alert in body["mine"]] == ["Travaux T2", "Info T2"]
    assert [alert["title"] for alert in body["network"]] == [
        "Travaux T2",
        "Info C9",
        "Info T2",
    ]
    assert body["stale"] is False


def test_get_line_map_gives_the_trace_and_ordered_stops(monkeypatch, tmp_path):
    lines = {"T2": Line("T2", "TRA", "#6BA230", stops={"A": ["33685", "32103"]})}
    positions = {"32103": (45.7, 4.8), "33685": (45.75, 4.83)}
    traces = {("T2", "A"): [[(45.75, 4.83), (45.7, 4.8)]]}
    start_without_network(monkeypatch, tmp_path / "favourites.json")
    monkeypatch.setattr(app_module, "load_network", lambda: (FAKE_PLATFORMS, lines))
    monkeypatch.setattr(app_module, "load_geometry", lambda: (positions, traces))

    with TestClient(app) as client:
        response = client.get("/api/lines/T2/A/map")
        unknown = client.get("/api/lines/ZZZ/A/map")

    assert response.json() == {
        "colour": "#6BA230",
        "trace": [[[45.75, 4.83], [45.7, 4.8]]],
        "stops": [
            {
                "platform": "33685",
                "name": "Bellecour A. Poncet",
                "lat": 45.75,
                "lon": 4.83,
            },
            {"platform": "32103", "name": "Perrache", "lat": 45.7, "lon": 4.8},
        ],
    }
    assert unknown.status_code == 404


def test_files_are_revalidated_but_not_the_api(monkeypatch, tmp_path):
    start_without_network(monkeypatch, tmp_path / "favourites.json")

    with TestClient(app) as client:
        page = client.get("/")
        api = client.get("/api/health")

    assert page.headers["cache-control"] == "no-cache"
    assert "cache-control" not in api.headers
