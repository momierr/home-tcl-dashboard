from dataclasses import replace
from datetime import datetime

import pytest

from home_tcl_dashboard.alerts import Alert
from home_tcl_dashboard.board import Banner, Card, Favourite, build_banner, build_card
from home_tcl_dashboard.network import Line, Platform
from home_tcl_dashboard.realtime import Departure


def test_build_card_for_perrache_t2() -> None:
    favourite = Favourite(line="T2", sens="A", platform="32103")
    platforms = {
        "32103": Platform(
            id="32103",
            name="Perrache",
            line_directions={("T1", "A"), ("T2", "A")},
        )
    }
    lines = {
        "T2": Line(
            code="T2",
            mode="TRA",
            colour="#009E3D",
            destinations={"A": "Saint-Priest Bel Air", "R": "Perrache"},
        )
    }
    t2 = Departure(
        line="T2", platform="32103", time=datetime(2026, 10, 16, 8, 5), realtime=True
    )
    t1 = Departure(
        line="T1", platform="32103", time=datetime(2026, 10, 16, 8, 3), realtime=True
    )
    now = datetime(2026, 10, 16, 8, 0)

    card = build_card(favourite, platforms, lines, [t2, t1], [], now)

    assert card == Card(
        line="T2",
        platform_name="Perrache",
        destination="Saint-Priest Bel Air",
        departures=[t2],
        disrupted=False,
    )


def test_build_card_keeps_only_departures_of_its_platform() -> None:
    favourite = Favourite(line="T2", sens="A", platform="32103")
    platforms = {
        "32103": Platform(id="32103", name="Perrache", line_directions={("T2", "A")})
    }
    lines = {
        "T2": Line("T2", "TRA", "#6BA230", {"A": "Saint-Priest Bel Air"}),
    }
    here = Departure("T2", "32103", datetime(2026, 10, 16, 8, 5), realtime=True)
    elsewhere = Departure("T2", "99999", datetime(2026, 10, 16, 8, 3), realtime=True)
    now = datetime(2026, 10, 16, 8, 0)

    card = build_card(favourite, platforms, lines, [here, elsewhere], [], now)

    assert card.departures == [here]


def alert_on(line: str, kind: str) -> Alert:
    return Alert(
        line=line,
        kind=kind,
        severity=20,
        start=datetime(2026, 10, 1),
        end=datetime(2026, 10, 31),
        title="Travaux",
        message="Circulation partielle.",
    )


@pytest.mark.parametrize(
    "alert, disrupted",
    [
        (alert_on("T2", "Perturbation"), True),
        (alert_on("T1", "Perturbation"), False),
        (alert_on("T2", "Information"), False),
    ],
)
def test_build_card_is_disrupted_by_a_perturbation_on_its_line(
    alert: Alert, disrupted: bool
) -> None:
    favourite = Favourite(line="T2", sens="A", platform="32103")
    platforms = {
        "32103": Platform(id="32103", name="Perrache", line_directions={("T2", "A")})
    }
    lines = {
        "T2": Line("T2", "TRA", "#6BA230", {"A": "Saint-Priest Bel Air"}),
    }
    now = datetime(2026, 10, 16, 8, 0)

    card = build_card(favourite, platforms, lines, [], [alert], now)

    assert card.disrupted is disrupted


def test_build_banner_shows_the_most_serious_alert_on_favourite_lines() -> None:
    favourites = [Favourite(line="T2", sens="A", platform="32103")]
    info = replace(alert_on("T2", "Information"), severity=30, title="Ascenseur")
    works = replace(alert_on("T2", "Perturbation"), severity=20, title="Travaux")
    elsewhere = replace(alert_on("C9", "Perturbation"), severity=10, title="Accident")

    banner = build_banner(favourites, [info, works, elsewhere])

    assert banner == Banner(line="T2", title="Travaux", count=2)


def test_build_banner_is_none_without_alerts_on_favourite_lines() -> None:
    favourites = [Favourite(line="T2", sens="A", platform="32103")]

    assert build_banner(favourites, [alert_on("C9", "Perturbation")]) is None
