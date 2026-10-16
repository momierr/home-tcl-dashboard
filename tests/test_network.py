from home_tcl_dashboard.network import (
    Line,
    Platform,
    line_sort_key,
    lines_of_mode,
    next_stops,
    parse_desserte,
    parse_lines,
    parse_platform,
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
