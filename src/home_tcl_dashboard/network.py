import re
from dataclasses import dataclass, field

PREFIX_ORDER = ["C", "", "N", "A", "T", "TB", "PL", "J"]


@dataclass
class Platform:
    id: str
    name: str
    line_directions: set[tuple[str, str]]


@dataclass
class Line:
    code: str
    mode: str
    colour: str
    destinations: dict[str, str] = field(default_factory=dict)
    stops: dict[str, list[str]] = field(default_factory=dict)  # sens -> platform ids


def parse_desserte(desserte: str) -> set[tuple[str, str]]:
    """Transform 'B:A,C12:R' into {('B', 'A'), ('C12', 'R')}."""
    line_directions = set()
    for item in desserte.split(","):
        line, direction = item.split(":")
        line_directions.add((line, direction))
    return line_directions


def parse_platform(row: dict[str, str]) -> Platform:
    return Platform(
        id=row["id"],
        name=row["nom"],
        line_directions=parse_desserte(row["desserte"]),
    )


def parse_lines(rows: list[dict[str, str]]) -> dict[str, Line]:
    """One line per code_ligne, with its destination for each direction."""
    lines: dict[str, Line] = {}
    for row in rows:
        code = row["code_ligne"]
        if code not in lines:
            lines[code] = Line(code, row["famille_transport"], row["couleur_hex"])
        sens = row["sens"][0]
        if sens not in lines[code].destinations:
            lines[code].destinations[sens] = row["nom_destination"]

    return lines


def line_sort_key(code: str, mode: str) -> tuple[int, str, int, str]:
    """Natural order ('C9' < 'C10'); bus prefixes follow PREFIX_ORDER."""
    match = re.fullmatch(r"([A-Z]*)(\d*)(.*)", code)
    assert match is not None
    prefix, number, suffix = match.groups()
    rank = 0
    if mode == "bus":
        rank = (
            PREFIX_ORDER.index(prefix) if prefix in PREFIX_ORDER else len(PREFIX_ORDER)
        )
    return rank, prefix, int(number or 0), suffix
