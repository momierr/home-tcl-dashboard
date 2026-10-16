import re
from dataclasses import dataclass, field

PREFIX_ORDER = ["C", "", "N", "A", "T", "TB", "PL", "J"]
Point = tuple[float, float]  # (lat, lon), as the WFS and Leaflet use them

MODES = {"MET": "metro", "FUN": "metro", "TRA": "tram", "BUS": "bus"}


def clean_text(text: str) -> str:
    """Grand Lyon text: 'Gare Part  Dieu' -> 'Gare Part Dieu', drops a dangling ' -'."""
    return re.sub(r"\s+[-.]+$", "", " ".join(text.split()))


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
        name=clean_text(row["nom"]),
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
            lines[code].destinations[sens] = clean_text(row["nom_destination"])

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


def lines_of_mode(lines: dict[str, Line], mode: str) -> list[Line]:
    """The lines of a tab (metro, tram or bus) that have stops, in natural_order."""
    return sorted(
        [line for line in lines.values() if MODES[line.mode] == mode and line.stops],
        key=lambda line: line_sort_key(line.code, mode),
    )


def next_stops(stops: list[str], platform: str, n: int = 7) -> tuple[list[str], int]:
    """The n stops from `platform` on (itself first), and how many come after them."""
    start = stops.index(platform)
    shown = stops[start : start + n]
    return shown, len(stops) - start - len(shown)


def timeline(
    stops: list[str], platform: str, platforms: dict[str, Platform], n: int = 7
) -> tuple[list[str], int]:
    """Names of the next n stops from `platform`, and how many come after them.

    A platform off the line's longest trip (a twin platform, a variant stop) is
    found by its station name; if the station is not on the trip, only it is shown.
    """
    name = platforms[platform].name
    names = [platforms[stop].name for stop in stops]
    if name not in names:
        return [name], 0
    return next_stops(names, name, n)


def parse_points(wkt: str) -> list[Point]:
    """'POINT (45.75 4.83)' -> [(45.75, 4.83)]; works for any WKT geometry."""
    numbers = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", wkt)]
    return list(zip(numbers[::2], numbers[1::2], strict=True))


def parse_trace(wkt: str) -> list[list[Point]]:
    """'MULTILINESTRING ((a b, c d), (e f, g h))' -> one list of points per part."""
    return [parse_points(part) for part in re.findall(r"\(([^()]+)\)", wkt)]


def parse_traces(
    line_rows: list[dict[str, str]],
) -> dict[tuple[str, str], list[list[Point]]]:
    """(line, sens) -> its trace, from the first row of each direction."""
    traces: dict[tuple[str, str], list[list[Point]]] = {}
    for row in line_rows:
        key = (row["code_ligne"], row["sens"][0])  # "Aller" -> "A"
        if key not in traces:  # some lines have 2 traces per sens
            traces[key] = parse_trace(row["the_geom"])
    return traces
