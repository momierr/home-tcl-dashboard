import csv
import io
import os

import requests
from dotenv import load_dotenv

WFS_URL = "https://data.grandlyon.com/geoserver/sytral/ows"
BASE = "https://data.grandlyon.com/fr/datapusher/ws/rdata"

csv.field_size_limit(10**8)


def get_auth() -> tuple[str, str]:
    load_dotenv()
    return os.environ["GDL_USER"], os.environ["GDL_PWD"]


def fetch_wfs(layer: str, properties: str) -> list[dict[str, str]]:
    """Rows of a Grand Lyon WFS Layer,  as dicts (CSV columns -> keys)."""
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "request": "GetFeature",
        "typename": f"sytral:tcl_sytral.{layer}",
        "outputFormat": "CSV",
        "propertyName": properties,
    }

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
