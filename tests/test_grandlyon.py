import requests

from home_tcl_dashboard.grandlyon import fetch_wfs

DUMMY_CSV = """id,nom,desserte
30101,Perrache,A:A
32103,Perrache,"T1:A,T2:A"
"""


class FakeResponse:
    text = DUMMY_CSV

    def raise_for_status(self) -> None:
        pass


def test_fetch_wfs_parses_csv_rows(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params)
        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    rows = fetch_wfs("tclarret", "id,nom,desserte")

    assert rows == [
        {"id": "30101", "nom": "Perrache", "desserte": "A:A"},
        {"id": "32103", "nom": "Perrache", "desserte": "T1:A,T2:A"},
    ]
    assert calls[0]["typename"] == "sytral:tcl_sytral.tclarret"
