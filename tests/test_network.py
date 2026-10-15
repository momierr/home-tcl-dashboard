from home_tcl_dashboard.network import Platform, parse_desserte, parse_platform


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
        id="32103", name="Perrache", line_directions=parse_desserte("T1:A,T2:A")
    )
