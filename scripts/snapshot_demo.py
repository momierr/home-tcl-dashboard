"""Record what the API answers right now into demo/, for the static demo on
GitHub Pages. Run it from the repository root, at a busy hour:

    pixi run python scripts/snapshot_demo.py
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder

from home_tcl_dashboard.board import Favourite
from home_tcl_dashboard.dashboard import Dashboard
from home_tcl_dashboard.grandlyon import GrandLyon
from home_tcl_dashboard.network import MODES

OUT = Path("demo")
# Bus traces are heavy (up to 190 kB each, 200+ of them): maps for rails only
MAPPED_TABS = {"metro", "tram"}


def write(path: Path, data: Any) -> None:
    """Save `data` as the JSON the API would answer (dataclasses, datetimes)."""
    path.write_text(json.dumps(jsonable_encoder(data), ensure_ascii=False))


def main() -> None:
    dashboard = Dashboard.load(GrandLyon.from_env(), Path("data"))
    now = datetime.now()
    for folder in ("stops", "maps", "detail"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)

    write(OUT / "snapshot.json", {"now": now, "favourites": dashboard.favourites})
    write(OUT / "alerts.json", dashboard.alerts_page(now))
    for tab in ("metro", "tram", "bus"):
        write(OUT / f"lines-{tab}.json", dashboard.lines_of(tab))

    # the stops shown in detail: every rail stop, plus the favourites (buses too)
    details = list(dashboard.favourites)
    for line in dashboard.lines.values():
        for sens, platforms in line.stops.items():
            name = f"{line.code}-{sens}.json"
            write(OUT / "stops" / name, dashboard.stops(line.code, sens))
            if MODES[line.mode] in MAPPED_TABS:
                write(OUT / "maps" / name, dashboard.line_map(line.code, sens))
                details.extend(
                    Favourite(line=line.code, sens=sens, platform=platform)
                    for platform in platforms
                )

    # One real-time call per stop (a few minutes): Grand Lyon answers 502 past
    # ~150 platforms in one call, and caps an answer at 1000 passages anyway
    for i, here in enumerate(details, 1):
        detail = dashboard.stop_detail(here.platform, here.line, here.sens, now)
        name = f"{here.platform}-{here.line}-{here.sens}.json"
        write(OUT / "detail" / name, detail)
        if i % 100 == 0:
            print(f"{i}/{len(details)} stops")
    print(f"{len(details)} stops recorded in {OUT}/ for {now:%Y-%m-%d %H:%M}")


if __name__ == "__main__":
    main()
