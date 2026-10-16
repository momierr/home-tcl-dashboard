import json
from dataclasses import asdict
from pathlib import Path

from home_tcl_dashboard.board import Favourite


def load_favourites(path: Path) -> list[Favourite]:
    if not path.exists():
        return []
    rows = json.loads(path.read_text())
    return [Favourite(**row) for row in rows]


def save_favourites(path: Path, favourites: list[Favourite]) -> None:
    path.parent.mkdir(exist_ok=True)
    rows = [asdict(favourite) for favourite in favourites]
    path.write_text(json.dumps(rows, indent=2))
