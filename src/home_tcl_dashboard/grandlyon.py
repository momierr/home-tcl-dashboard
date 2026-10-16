import csv
import datetime as dt
import io
import os
import zipfile
from pathlib import Path
from typing import Any, Self

import requests
from dotenv import load_dotenv

WFS_URL = "https://data.grandlyon.com/geoserver/sytral/ows"
GTFS_URL = "https://download.data.grandlyon.com/files/rdata/tcl_sytral.tcltheorique/GTFS_TCL.ZIP"
BASE = "https://data.grandlyon.com/fr/datapusher/ws/rdata"
PICTOS_URL = (
    "https://download.data.grandlyon.com/files/rdata/tcl_sytral.tclpictogrammes/"
    "Pictogrammes_lignes_complets.zip"
)

csv.field_size_limit(10**8)


class GrandLyon:
    def __init__(
        self, user: str, password: str, session: requests.Session | None = None
    ) -> None:

        self.session = session if session is not None else requests.Session()
        self.session.auth = (user, password)

    @classmethod
    def from_env(cls) -> Self:
        load_dotenv()
        return cls(os.environ["GDL_USER"], os.environ["GDL_PWD"])

    def fetch_wfs(
        self, layer: str, properties: str, cql_filter: str | None = None
    ) -> list[dict[str, str]]:
        """Rows of a Grand Lyon WFS layer, as dicts (CSV columns -> keys)."""
        params = {
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "request": "GetFeature",
            "typename": f"sytral:tcl_sytral.{layer}",
            "outputFormat": "CSV",
            "propertyName": properties,
        }
        if cql_filter is not None:
            params["CQL_FILTER"] = cql_filter

        response = self.session.get(WFS_URL, params=params, timeout=30)
        response.raise_for_status()
        return list(csv.DictReader(io.StringIO(response.text)))

    def fetch_passages(self, platform_ids: list[str]) -> list[dict]:
        response = self.session.get(
            f"{BASE}/tcl_sytral.tclpassagearret/all.json",
            params={"compact": "false", "id__in": ",".join(platform_ids)},
            timeout=10,
        )
        response.raise_for_status()
        passages = response.json()["values"]
        for p in passages:
            p["id"] = str(p["id"])
        return passages

    def fetch_alerts(self) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{BASE}/tcl_sytral.tclalertetrafic_2/all.json",
            params={"compact": "false"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["values"]

    def download_gtfs(self, path: Path) -> None:
        if (
            path.exists()
            and dt.date.fromtimestamp(path.stat().st_mtime) == dt.date.today()
        ):
            return
        response = self.session.get(GTFS_URL, timeout=120)
        response.raise_for_status()
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(response.content)

    def download_pictograms(self, directory: Path) -> None:
        """Extract the official line pictograms (A.svg, C9.svg...) into `directory`, once."""
        if directory.exists():
            return
        response = self.session.get(PICTOS_URL, timeout=60)
        response.raise_for_status()
        zipfile.ZipFile(io.BytesIO(response.content)).extractall(directory)
