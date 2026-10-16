import json
from dataclasses import asdict
from pathlib import Path

from home_tcl_dashboard.board import Favourite
from home_tcl_dashboard.network import Line, Platform

MAX_FAVOURITES = 6


def load_favourites(path: Path) -> list[Favourite]:
    if not path.exists():
        return []
    rows = json.loads(path.read_text())
    return [Favourite(**row) for row in rows]


def save_favourites(path: Path, favourites: list[Favourite]) -> None:
    path.parent.mkdir(exist_ok=True)
    rows = [asdict(favourite) for favourite in favourites]
    path.write_text(json.dumps(rows, indent=2))


def favourite_errors(
    favourites: list[Favourite],
    platforms: dict[str, Platform],
    lines: dict[str, Line],
) -> list[str]:
    """Why these favourites are invalid; empty if they are all fine."""
    errors: list[str] = []
    if len(favourites) > MAX_FAVOURITES:
        errors.append(f"at most {MAX_FAVOURITES} favourites")
    for favourite in favourites:
        if favourite.line not in lines:
            errors.append(f"unknown line {favourite.line}")
            continue
        if favourite.platform not in platforms:
            errors.append(f"unknown platform {favourite.platform}")
            continue
        platform = platforms[favourite.platform]
        if (favourite.line, favourite.sens) not in platform.line_directions:
            errors.append(
                f"line {favourite.line} sens {favourite.sens}"
                f" does not stop at {favourite.platform}"
            )
    return errors
