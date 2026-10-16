import csv
import datetime as dt
import io
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

WFS_URL = "https://data.grandlyon.com/geoserver/sytral/ows"
GTFS_URL = "https://download.data.grandlyon.com/files/rdata/tcl_sytral.tcltheorique/GTFS_TCL.ZIP"
BASE = "https://data.grandlyon.com/fr/datapusher/ws/rdata"

csv.field_size_limit(10**8)


def get_auth() -> tuple[str, str]:
    load_dotenv()
    return os.environ["GDL_USER"], os.environ["GDL_PWD"]


def fetch_wfs(
    layer: str, properties: str, cql_filter: str | None = None
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

    response = requests.get(WFS_URL, params=params, timeout=30)
    response.raise_for_status()
    return list(csv.DictReader(io.StringIO(response.text)))


def fetch_passages(platform_ids: list[str], auth: tuple[str, str]) -> list[dict]:
    response = requests.get(
        f"{BASE}/tcl_sytral.tclpassagearret/all.json",
        params={"compact": "false", "id__in": ",".join(platform_ids)},
        auth=auth,
        timeout=10,
    )
    response.raise_for_status()
    passages = response.json()["values"]
    for p in passages:
        p["id"] = str(p["id"])
    return passages


def fetch_alerts(auth: tuple[str, str]) -> list[dict[str, Any]]:
    response = requests.get(
        f"{BASE}/tcl_sytral.tclalertetrafic_2/all.json",
        params={"compact": "false"},
        auth=auth,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["values"]


def download_gtfs(path: Path, auth: tuple[str, str]) -> None:
    if path.exists() and dt.date.fromtimestamp(path.stat().st_mtime) == dt.date.today():
        return
    response = requests.get(GTFS_URL, auth=auth, timeout=120)
    response.raise_for_status()
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(response.content)
