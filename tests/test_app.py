from datetime import datetime

from fastapi.testclient import TestClient

from home_tcl_dashboard import app as app_module
from home_tcl_dashboard.app import app
from home_tcl_dashboard.board import Favourite
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
    monkeypatch.setattr(app_module, "load_scheduled_departures", lambda lines: [])
    monkeypatch.setattr(app_module, "get_auth", lambda: ("user", "pwd"))
    monkeypatch.setattr(app_module, "fetch_passages", fake_fetch_passages)
    monkeypatch.setattr(app_module, "fetch_alerts", lambda auth: [])

    with TestClient(app) as client:
        response = client.get("/api/board")

    assert response.status_code == 200
    assert response.json() == {
        "cards": [
            {
                "line": "T2",
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
        app_module, "FAVOURITES", [Favourite(line="A", sens="A", platform="30101")]
    )
    monkeypatch.setattr(app_module, "load_network", lambda: (platforms, lines))
    monkeypatch.setattr(
        app_module, "load_scheduled_departures", lambda lines: [scheduled]
    )
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
