import csv
import io

import requests

WFS_URL = "https://data.grandlyon.com/geoserver/sytral/ows"
csv.field_size_limit(10**8)


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
