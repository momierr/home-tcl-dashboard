import re
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


def parse_points(wkt: str) -> list[tuple[float, float]]:
    """'POINT (45.75 4.83)' or a MULTILINESTRING -> [(lat, lon), ...]."""
    numbers = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", wkt)]
    return list(zip(numbers[::2], numbers[1::2], strict=True))


def order_platforms(
    trace: list[tuple[float, float]], positions: dict[str, tuple[float, float]]
) -> list[str]:
    """Platform ids in travel order: each one sits at its closest vertex of the trace."""

    def closest_vertex(platform_id: str) -> int:
        lat, lon = positions[platform_id]
        return min(
            range(len(trace)),
            key=lambda i: (trace[i][0] - lat) ** 2 + (trace[i][1] - lon) ** 2,
        )

    return sorted(positions, key=closest_vertex)
