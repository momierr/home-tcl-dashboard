from pathlib import Path

from home_tcl_dashboard.board import Favourite
from home_tcl_dashboard.favourites import load_favourites, save_favourites


def test_load_favourites_is_empty_without_a_file(tmp_path: Path) -> None:
    assert load_favourites(tmp_path / "favourites.json") == []


def test_saved_favourites_load_back_in_the_same_order(tmp_path: Path) -> None:
    path = tmp_path / "data" / "favourites.json"
    favourites = [
        Favourite(line="T2", sens="A", platform="32103"),
        Favourite(line="A", sens="A", platform="30101"),
        Favourite(line="C9", sens="A", platform="33685"),
    ]

    save_favourites(path, favourites)

    assert load_favourites(path) == favourites
