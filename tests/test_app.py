from fastapi.testclient import TestClient

from home_tcl_dashboard import app as app_module
from home_tcl_dashboard.app import app
from home_tcl_dashboard.network import Line, Platform

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
