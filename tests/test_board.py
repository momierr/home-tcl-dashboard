from datetime import datetime

from home_tcl_dashboard.board import Card, Favourite, build_card
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

    card = build_card(favourite, platforms, lines, [t2, t1], now)

    assert card == Card(
        line="T2",
        platform_name="Perrache",
        destination="Saint-Priest Bel Air",
        departures=[t2],
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

    card = build_card(favourite, platforms, lines, [here, elsewhere], now)

    assert card.departures == [here]
