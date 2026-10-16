import io
import os
import time
import zipfile

from home_tcl_dashboard.grandlyon import GrandLyon

DUMMY_CSV = """id,nom,desserte
30101,Perrache,A:A
32103,Perrache,"T1:A,T2:A"
"""


class FakeResponse:
    text = DUMMY_CSV

    def raise_for_status(self) -> None:
        pass


class FakeSession:
    """Stands in for requests.Session: notes each call, answers `response`."""

    def __init__(self, response=None):
        self.auth = None
        self.response = response
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params})
        if self.response is None:
            raise AssertionError("should not call Grand Lyon")
        return self.response


def client_with(response=None):
    session = FakeSession(response)
    return GrandLyon("user", "pwd", session=session), session


def test_the_client_sends_the_credentials_with_every_call():
    _, session = client_with()

    assert session.auth == ("user", "pwd")


def test_fetch_wfs_parses_csv_rows():
    client, session = client_with(FakeResponse())

    rows = client.fetch_wfs("tclarret", "id,nom,desserte")

    assert rows == [
        {"id": "30101", "nom": "Perrache", "desserte": "A:A"},
        {"id": "32103", "nom": "Perrache", "desserte": "T1:A,T2:A"},
    ]
    assert session.calls[0]["params"]["typename"] == "sytral:tcl_sytral.tclarret"


def test_fetch_wfs_sends_cql_filter():
    client, session = client_with(FakeResponse())

    client.fetch_wfs("tcllignebus_2_0_0", "code_ligne", cql_filter="type_trace='NOM'")

    assert session.calls[0]["params"]["CQL_FILTER"] == "type_trace='NOM'"


def test_fetch_wfs_sends_no_cql_filter_by_default():
    client, session = client_with(FakeResponse())

    client.fetch_wfs("tclarret", "id")

    assert "CQL_FILTER" not in session.calls[0]["params"]


class FakeJsonResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self):
        return {
            "values": [
                {"id": 32103, "ligne": "T2", "heurepassage": "2026-10-15 23:55:44"},
            ]
        }


def test_fetch_passages_returns_values_with_string_ids():
    client, session = client_with(FakeJsonResponse())

    passages = client.fetch_passages(["32103", "30101"])

    assert passages == [
        {"id": "32103", "ligne": "T2", "heurepassage": "2026-10-15 23:55:44"},
    ]
    assert session.calls[0]["params"]["id__in"] == "32103,30101"


class FakeZipResponse:
    content = b"new zip"

    def raise_for_status(self) -> None:
        pass


def test_download_gtfs_fetches_when_missing(tmp_path):
    path = tmp_path / "data" / "gtfs.zip"
    client, _ = client_with(FakeZipResponse())

    client.download_gtfs(path)

    assert path.read_bytes() == b"new zip"


def test_download_gtfs_skips_when_downloaded_today(tmp_path):
    path = tmp_path / "gtfs.zip"
    path.write_bytes(b"old zip")
    client, _ = client_with()  # any call would fail

    client.download_gtfs(path)

    assert path.read_bytes() == b"old zip"


def test_download_gtfs_fetches_again_the_next_day(tmp_path):
    path = tmp_path / "gtfs.zip"
    path.write_bytes(b"old zip")
    yesterday = time.time() - 24 * 3600
    os.utime(path, (yesterday, yesterday))
    client, _ = client_with(FakeZipResponse())

    client.download_gtfs(path)

    assert path.read_bytes() == b"new zip"


class FakeAlertsResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self):
        return {"values": [{"ligne_cli": "D", "niveauseverite": 20}]}


def test_fetch_alerts_returns_values():
    client, session = client_with(FakeAlertsResponse())

    alerts = client.fetch_alerts()

    assert alerts == [{"ligne_cli": "D", "niveauseverite": 20}]
    assert session.calls[0]["url"].endswith("tcl_sytral.tclalertetrafic_2/all.json")


class FakePictosResponse:
    def raise_for_status(self) -> None:
        pass

    @property
    def content(self) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("A.svg", "<svg/>")
        return buffer.getvalue()


def test_download_pictograms_extracts_the_svgs(tmp_path):
    client, _ = client_with(FakePictosResponse())

    client.download_pictograms(tmp_path / "pictos")

    assert (tmp_path / "pictos" / "A.svg").read_text() == "<svg/>"


def test_download_pictograms_skips_when_already_there(tmp_path):
    (tmp_path / "pictos").mkdir()
    client, _ = client_with()  # any call would fail

    client.download_pictograms(tmp_path / "pictos")
