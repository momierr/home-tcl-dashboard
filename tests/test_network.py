from home_tcl_dashboard.network import (
    Line,
    Platform,
    order_platforms,
    parse_desserte,
    parse_lines,
    parse_platform,
    parse_points,
)


def test_parse_desserte_single_line():
    assert parse_desserte("A:A") == {("A", "A")}


def test_parse_desserte_several_lines_same_direction():
    assert parse_desserte("T1:A,T2:A") == {("T1", "A"), ("T2", "A")}


def test_parse_desserte_same_line_several_directions():
    assert parse_desserte("108:R,108:A") == {("108", "R"), ("108", "A")}


def test_parse_platform():
    assert parse_platform(
        {"id": "32103", "nom": "Perrache", "desserte": "T1:A,T2:A"}
    ) == Platform(
        id="32103", name="Perrache", line_directions={("T1", "A"), ("T2", "A")}
    )


def test_parse_lines_groups_both_directions():
    rows = [
        {
            "code_ligne": "A",
            "sens": "Aller",
            "nom_destination": "Vaulx-en-Velin La Soie",
            "famille_transport": "MET",
            "couleur_hex": "#E8308A",
        },
        {
            "code_ligne": "A",
            "sens": "Retour",
            "nom_destination": "Perrache",
            "famille_transport": "MET",
            "couleur_hex": "#E8308A",
        },
    ]

    assert parse_lines(rows) == {
        "A": Line(
            code="A",
            mode="MET",
            colour="#E8308A",
            destinations={"A": "Vaulx-en-Velin La Soie", "R": "Perrache"},
        )
    }


def test_parse_lines_keeps_first_trace_of_a_direction():
    rows = [
        {
            "code_ligne": "43",
            "sens": "Aller",
            "nom_destination": "First",
            "famille_transport": "BUS",
            "couleur_hex": "#000000",
        },
        {
            "code_ligne": "43",
            "sens": "Aller",
            "nom_destination": "Second",
            "famille_transport": "BUS",
            "couleur_hex": "#000000",
        },
    ]

    assert parse_lines(rows)["43"].destinations == {"A": "First"}


def test_parse_points_point() -> None:
    assert parse_points("POINT (45.75 4.83)") == [(45.75, 4.83)]


def test_parse_points_multilinestring_with_negative_values() -> None:
    wkt = "MULTILINESTRING ((45.7 -4.8, 45.8 -4.9), (46 5))"

    assert parse_points(wkt) == [(45.7, -4.8), (45.8, -4.9), (46.0, 5.0)]


def test_order_platforms_follows_the_trace() -> None:
    trace = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]
    positions = {
        "third": (2.1, 0.1),
        "first": (0.1, -0.1),
        "second": (0.9, 0.2),
    }

    assert order_platforms(trace, positions) == ["first", "second", "third"]


def test_order_platforms_follows_the_direction_of_the_trace() -> None:
    there = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
    back = list(reversed(there))
    positions = {"start": (0.0, 0.0), "end": (2.0, 0.0)}

    assert order_platforms(there, positions) == ["start", "end"]
    assert order_platforms(back, positions) == ["end", "start"]
