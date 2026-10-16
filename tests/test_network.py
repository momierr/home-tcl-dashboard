import pytest

from home_tcl_dashboard.network import (
    Line,
    Platform,
    clean_text,
    line_sort_key,
    lines_of_mode,
    next_stops,
    parse_desserte,
    parse_lines,
    parse_platform,
    parse_points,
    parse_trace,
    parse_traces,
    timeline,
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


def test_line_sort_key_metro_is_alphabetical() -> None:
    codes = ["D", "F2", "A", "C", "F1", "B"]

    result = sorted(codes, key=lambda code: line_sort_key(code, "metro"))

    assert result == ["A", "B", "C", "D", "F1", "F2"]


def test_line_sort_key_bus_follows_prefix_order() -> None:
    codes = ["J501", "PL1", "TB11", "T36", "A71", "N181", "33", "C10", "C9", "XYZ1"]

    result = sorted(codes, key=lambda code: line_sort_key(code, "bus"))

    assert result == [
        "C9",
        "C10",
        "33",
        "N181",
        "A71",
        "T36",
        "TB11",
        "PL1",
        "J501",
        "XYZ1",
    ]


def test_line_sort_key_numbers_are_natural() -> None:
    codes = ["102", "98EX", "33", "98"]

    result = sorted(codes, key=lambda code: line_sort_key(code, "bus"))

    assert result == ["33", "98", "98EX", "102"]


def test_lines_of_mode_keeps_the_tab_lines_with_stops_in_order() -> None:
    lines = {
        "F1": Line("F1", "FUN", "#992358", stops={"A": ["30212"]}),
        "A": Line("A", "MET", "#E8308A", stops={"A": ["30101"]}),
        "C9": Line("C9", "BUS", "#C88817", stops={"A": ["33685"]}),
        "Z": Line("Z", "MET", "#000000"),
    }

    tab = lines_of_mode(lines, "metro")

    assert [line.code for line in tab] == ["A", "F1"]


STOPS = ["a", "b", "c", "d", "e"]


def test_next_stops_starts_at_the_platform() -> None:
    assert next_stops(STOPS, "b", n=2) == (["b", "c"], 2)


def test_next_stops_near_the_terminus_has_nothing_left() -> None:
    assert next_stops(STOPS, "d", n=7) == (["d", "e"], 0)


def test_next_stops_at_the_terminus_is_only_itself() -> None:
    assert next_stops(STOPS, "e") == (["e"], 0)


TIMELINE_PLATFORMS = {
    "1": Platform(id="1", name="Gare de Vaise", line_directions={("D", "A")}),
    "2": Platform(id="2", name="Vieux Lyon", line_directions={("D", "A")}),
    "2bis": Platform(id="2bis", name="Vieux Lyon", line_directions={("D", "A")}),
    "3": Platform(id="3", name="Bellecour", line_directions={("D", "A")}),
    "9": Platform(id="9", name="Variante", line_directions={("D", "A")}),
}


def test_timeline_starts_at_the_platform_station() -> None:
    assert timeline(["1", "2", "3"], "2", TIMELINE_PLATFORMS, n=2) == (
        ["Vieux Lyon", "Bellecour"],
        0,
    )


def test_timeline_finds_a_twin_platform_by_its_station_name() -> None:
    assert timeline(["1", "2", "3"], "2bis", TIMELINE_PLATFORMS) == (
        ["Vieux Lyon", "Bellecour"],
        0,
    )


def test_timeline_shows_only_a_stop_that_is_not_on_the_trip() -> None:
    assert timeline(["1", "2", "3"], "9", TIMELINE_PLATFORMS) == (["Variante"], 0)


def test_parse_points_point() -> None:
    assert parse_points("POINT (45.75 4.83)") == [(45.75, 4.83)]


def test_parse_points_with_negative_values() -> None:
    assert parse_points("LINESTRING (45.7 -4.8, 46 5)") == [(45.7, -4.8), (46.0, 5.0)]


def test_parse_trace_keeps_the_parts_apart() -> None:
    wkt = "MULTILINESTRING ((45.0 4.0, 45.1 4.1), (46.0 5.0, 46.1 5.1))"

    assert parse_trace(wkt) == [
        [(45.0, 4.0), (45.1, 4.1)],
        [(46.0, 5.0), (46.1, 5.1)],
    ]


def test_parse_traces_keeps_the_first_trace_of_a_direction() -> None:
    rows = [
        {
            "code_ligne": "43",
            "sens": "Aller",
            "the_geom": "MULTILINESTRING ((1 1, 2 2))",
        },
        {
            "code_ligne": "43",
            "sens": "Aller",
            "the_geom": "MULTILINESTRING ((9 9, 8 8))",
        },
        {
            "code_ligne": "43",
            "sens": "Retour",
            "the_geom": "MULTILINESTRING ((2 2, 1 1))",
        },
    ]

    assert parse_traces(rows) == {
        ("43", "A"): [[(1.0, 1.0), (2.0, 2.0)]],
        ("43", "R"): [[(2.0, 2.0), (1.0, 1.0)]],
    }


@pytest.mark.parametrize(
    "raw, clean",
    [
        ("Gare Part  Dieu", "Gare Part Dieu"),
        ("Charpennes Charles Hernu .", "Charpennes Charles Hernu"),
        ("D\u00e9vi\u00e9e deux sens -", "D\u00e9vi\u00e9e deux sens"),
        ("St-Genis-Laval H\u00f4p. Sud", "St-Genis-Laval H\u00f4p. Sud"),
        ("Vieux Lyon Cat.St Jean", "Vieux Lyon Cat.St Jean"),
    ],
)
def test_clean_text(raw: str, clean: str) -> None:
    assert clean_text(raw) == clean
