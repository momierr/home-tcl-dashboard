import os
import time

import requests

from home_tcl_dashboard.grandlyon import download_gtfs, fetch_passages, fetch_wfs

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


def test_fetch_wfs_sends_cql_filter(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params)
        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    fetch_wfs("tcllignebus_2_0_0", "code_ligne", cql_filter="type_trace='NOM'")

    assert calls[0]["CQL_FILTER"] == "type_trace='NOM'"


def test_fetch_wfs_sends_no_cql_filter_by_default(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params)
        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    fetch_wfs("tclarret", "id")

    assert "CQL_FILTER" not in calls[0]


class FakeJsonResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self):
        return {
            "values": [
                {"id": 32103, "ligne": "T2", "heurepassage": "2026-10-15 23:55:44"},
            ]
        }


def test_fetch_passages_returns_values_with_string_ids(monkeypatch):
    calls = []

    def fake_get(url, params, auth, timeout):
        calls.append({"params": params, "auth": auth})
        return FakeJsonResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    passages = fetch_passages(["32103", "30101"], auth=("user", "pwd"))

    assert passages == [
        {"id": "32103", "ligne": "T2", "heurepassage": "2026-10-15 23:55:44"},
    ]
    assert calls[0]["params"]["id__in"] == "32103,30101"
    assert calls[0]["auth"] == ("user", "pwd")


class FakeZipResponse:
    content = b"new zip"

    def raise_for_status(self) -> None:
        pass


def test_download_gtfs_fetches_when_missing(tmp_path, monkeypatch):
    path = tmp_path / "data" / "gtfs.zip"
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeZipResponse())

    download_gtfs(path, ("user", "pwd"))

    assert path.read_bytes() == b"new zip"


def test_download_gtfs_skips_when_downloaded_today(tmp_path, monkeypatch):
    path = tmp_path / "gtfs.zip"
    path.write_bytes(b"old zip")

    def no_network(*args, **kwargs):
        raise AssertionError("should not download again")

    monkeypatch.setattr(requests, "get", no_network)

    download_gtfs(path, ("user", "pwd"))

    assert path.read_bytes() == b"old zip"


def test_download_gtfs_fetches_again_the_next_day(tmp_path, monkeypatch):
    path = tmp_path / "gtfs.zip"
    path.write_bytes(b"old zip")
    yesterday = time.time() - 24 * 3600
    os.utime(path, (yesterday, yesterday))
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeZipResponse())

    download_gtfs(path, ("user", "pwd"))

    assert path.read_bytes() == b"new zip"
