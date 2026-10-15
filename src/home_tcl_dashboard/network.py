from dataclasses import dataclass, field


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
