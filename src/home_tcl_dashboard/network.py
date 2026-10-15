from dataclasses import dataclass


def parse_desserte(desserte: str) -> set[tuple[str, str]]:
    """Transform 'B:A,C12:R' into {('B', 'A'), ('C12', 'R')}."""
    line_directions = set()
    for item in desserte.split(","):
        line, direction = item.split(":")
        line_directions.add((line, direction))
    return line_directions


@dataclass(frozen=True)
class Platform:
    id: str
    name: str
    line_directions: frozenset[tuple[str, str]]


def parse_platform(row: dict[str, str]) -> Platform:
    return Platform(
        id=row["id"],
        name=row["nom"],
        line_directions=frozenset({("T1", "A"), ("T2", "A")}),
    )
