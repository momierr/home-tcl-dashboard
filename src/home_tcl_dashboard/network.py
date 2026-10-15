def parse_desserte(desserte: str) -> set[tuple[str, str]]:
    """Transform 'B:A,C12:R' into {('B', 'A'), ('C12', 'R')}."""
    line_directions = set()
    for item in desserte.split(","):
        line, direction = item.split(":")
        line_directions.add((line, direction))
    return line_directions
