from pathlib import Path

import pytest

from home_tcl_dashboard.board import Favourite
from home_tcl_dashboard.favourites import (
    favourite_errors,
    load_favourites,
    save_favourites,
)
from home_tcl_dashboard.network import Line, Platform


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


PLATFORMS = {
    "32103": Platform(id="32103", name="Perrache", line_directions={("T2", "A")})
}
LINES = {"T2": Line("T2", "TRA", "#6BA230", {"A": "Saint-Priest Bel Air"})}
VALID = Favourite(line="T2", sens="A", platform="32103")


def test_favourite_errors_accepts_valid_favourites() -> None:
    assert favourite_errors([VALID], PLATFORMS, LINES) == []


def test_favourite_errors_refuses_more_than_six_favourites() -> None:
    assert favourite_errors([VALID] * 7, PLATFORMS, LINES) == ["at most 6 favourites"]


@pytest.mark.parametrize(
    "favourite, error",
    [
        (
            Favourite(line="ZZZ", sens="A", platform="32103"),
            "unknown line ZZZ",
        ),
        (
            Favourite(line="T2", sens="A", platform="99999"),
            "unknown platform 99999",
        ),
        (
            Favourite(line="T2", sens="R", platform="32103"),
            "line T2 sens R does not stop at 32103",
        ),
    ],
)
def test_favourite_errors_explains_each_invalid_favourite(
    favourite: Favourite, error: str
) -> None:
    assert favourite_errors([VALID, favourite], PLATFORMS, LINES) == [error]
