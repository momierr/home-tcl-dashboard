"""Test doubles shared by the test files: no network, no .env."""

from home_tcl_dashboard.dashboard import Dashboard
from home_tcl_dashboard.favourites import save_favourites
from home_tcl_dashboard.grandlyon import GrandLyon
from home_tcl_dashboard.network import Line, Platform


class FakeGrandLyon(GrandLyon):
    """No network: each test gives the answers it needs."""

    def __init__(self, passages=None, alerts=None, wfs=None, gtfs=None):
        super().__init__("user", "pwd")
        self.passages = passages or (lambda platform_ids: [])
        self.alerts = alerts or list
        self.wfs = wfs
        self.gtfs = gtfs or (lambda path: None)
        self.pictos_dir = None

    def fetch_passages(self, platform_ids):
        return self.passages(platform_ids)

    def fetch_alerts(self):
        return self.alerts()

    def fetch_wfs(self, layer, properties, cql_filter=None):
        return self.wfs(layer, properties, cql_filter)

    def download_gtfs(self, path):
        self.gtfs(path)

    def download_pictograms(self, directory):
        self.pictos_dir = directory


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


def make_dashboard(
    tmp_path,
    lines=FAKE_LINES,
    client=None,
    positions=None,
    traces=None,
    platforms=FAKE_PLATFORMS,
    favourites=None,
):
    """A Dashboard built by hand: no download, data kept in tmp_path."""
    if favourites is not None:
        save_favourites(tmp_path / "favourites.json", favourites)
    return Dashboard(
        client=client or FakeGrandLyon(),
        data_dir=tmp_path,
        platforms=platforms,
        lines=lines,
        positions=positions or {},
        traces=traces or {},
    )
