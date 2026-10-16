from datetime import date, datetime, timedelta

import pytest
import requests
from fakes import FAKE_LINES, FakeGrandLyon, make_dashboard

from home_tcl_dashboard import dashboard as dashboard_module
from home_tcl_dashboard.alerts import Alert
from home_tcl_dashboard.board import Card, Favourite
from home_tcl_dashboard.dashboard import (
    REGULAR_TRACES,
    Dashboard,
    InvalidFavourites,
    LineMap,
    LineSummary,
    MapStop,
    NotFound,
    StopSummary,
    load_network,
)
from home_tcl_dashboard.favourites import load_favourites, save_favourites
from home_tcl_dashboard.network import Line, Platform
from home_tcl_dashboard.realtime import Departure

PLATFORM_ROWS = [{"id": "32103", "nom": "Perrache", "desserte": "T1:A,T2:A"}]
LINE_ROWS = {
    "tcllignemf_2_0_0": [],
    "tcllignetram_2_0_0": [
        {
            "code_ligne": "T2",
            "sens": "Aller",
            "nom_destination": "Saint-Priest Bel Air",
            "famille_transport": "TRA",
            "couleur_hex": "#6BA230",
        }
    ],
    "tcllignebus_2_0_0": [
        {
            "code_ligne": "C9",
            "sens": "Aller",
            "nom_destination": "Hopitaux Est",
            "famille_transport": "BUS",
            "couleur_hex": "#C88817",
        }
    ],
}


def fake_fetch_wfs(layer, properties, cql_filter=None):
    if layer == "tclarret":
        return PLATFORM_ROWS
    assert cql_filter == REGULAR_TRACES
    return LINE_ROWS[layer]


def test_load_network_indexes_platforms_and_lines():
    platforms, lines = load_network(FakeGrandLyon(wfs=fake_fetch_wfs))

    assert platforms == {
        "32103": Platform(
            id="32103", name="Perrache", line_directions={("T1", "A"), ("T2", "A")}
        )
    }
    assert lines == {
        "T2": Line("T2", "TRA", "#6BA230", {"A": "Saint-Priest Bel Air"}),
        "C9": Line("C9", "BUS", "#C88817", {"A": "Hopitaux Est"}),
    }


def test_lines_of_lists_one_tab_with_stops_only(tmp_path):
    # lines_of_mode skips lines without stops, so only T2 has some here
    lines = {
        "T2": Line(
            "T2",
            "TRA",
            "#6BA230",
            {"A": "Saint-Priest Bel Air"},
            stops={"A": ["32103"]},
        ),
        "T1": Line("T1", "TRA", "#0D4F9E", {"A": "IUT - Feyssine"}),
        "C9": Line(
            "C9", "BUS", "#C88817", {"A": "Hopitaux Est"}, stops={"A": ["33685"]}
        ),
    }
    dashboard = make_dashboard(tmp_path, lines=lines)

    assert dashboard.lines_of("tram") == [
        LineSummary(
            code="T2", colour="#6BA230", destinations={"A": "Saint-Priest Bel Air"}
        )
    ]


def test_a_new_dashboard_has_no_favourites(tmp_path):
    assert make_dashboard(tmp_path).favourites == []


def test_a_dashboard_loads_the_saved_favourites(tmp_path):
    saved = [Favourite(line="C9", sens="A", platform="33685")]
    save_favourites(tmp_path / "favourites.json", saved)

    assert make_dashboard(tmp_path).favourites == saved


# T2 runs one way only here, from Bellecour to Perrache
ONE_WAY_T2 = {"T2": Line("T2", "TRA", "#6BA230", stops={"A": ["33685", "32103"]})}


def test_stops_lists_a_direction_in_travel_order(tmp_path):
    dashboard = make_dashboard(tmp_path, lines=ONE_WAY_T2)

    assert dashboard.stops("T2", "A") == [
        StopSummary(platform="33685", name="Bellecour A. Poncet"),
        StopSummary(platform="32103", name="Perrache"),
    ]


@pytest.mark.parametrize(
    "code, sens",
    [
        ("ZZZ", "A"),  # unknown line
        ("T2", "R"),  # one-way line: no stops that way
    ],
)
def test_stops_and_line_map_refuse_unknown_directions(tmp_path, code, sens):
    dashboard = make_dashboard(tmp_path, lines=ONE_WAY_T2)

    with pytest.raises(NotFound):
        dashboard.stops(code, sens)
    with pytest.raises(NotFound):
        dashboard.line_map(code, sens)


def test_line_map_gives_the_trace_and_the_located_stops(tmp_path):
    # Perrache has no position: it is left off the map
    positions = {"33685": (45.75, 4.83)}
    traces = {("T2", "A"): [[(45.75, 4.83), (45.7, 4.8)]]}
    dashboard = make_dashboard(
        tmp_path, lines=ONE_WAY_T2, positions=positions, traces=traces
    )

    assert dashboard.line_map("T2", "A") == LineMap(
        colour="#6BA230",
        trace=[[(45.75, 4.83), (45.7, 4.8)]],
        stops=[MapStop("33685", "Bellecour A. Poncet", 45.75, 4.83)],
    )


def fake_build(calls):
    """A build_departures that notes what it was asked for."""

    def build(path, days, lines):
        calls.append({"path": path, "days": days, "lines": lines})
        return []

    return build


def test_refresh_timetable_rebuilds_once_a_day(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(dashboard_module, "build_departures", fake_build(calls))
    dashboard = make_dashboard(tmp_path)

    dashboard.refresh_timetable(date(2026, 10, 16))
    dashboard.refresh_timetable(date(2026, 10, 16))
    dashboard.refresh_timetable(date(2026, 10, 17))

    assert [call["days"][-1] for call in calls] == [
        date(2026, 10, 16),
        date(2026, 10, 17),
    ]
    assert dashboard.scheduled_for == date(2026, 10, 17)


def test_the_timetable_covers_yesterday_and_today_for_the_metro_only(
    monkeypatch, tmp_path
):
    calls = []
    monkeypatch.setattr(dashboard_module, "build_departures", fake_build(calls))
    lines = {
        "A": Line("A", "MET", "#E8308A", {"A": "Vaulx-en-Velin La Soie"}),
        "T2": Line("T2", "TRA", "#6BA230", {"A": "Saint-Priest Bel Air"}),
    }

    make_dashboard(tmp_path, lines=lines).refresh_timetable(date(2026, 10, 16))

    assert calls == [
        {
            "path": tmp_path / "GTFS_TCL.ZIP",
            "days": [date(2026, 10, 15), date(2026, 10, 16)],
            "lines": {"A"},
        }
    ]


def down(path):
    raise requests.ConnectionError()


def test_refresh_timetable_keeps_the_old_file_when_download_fails(
    monkeypatch, tmp_path
):
    (tmp_path / "GTFS_TCL.ZIP").write_bytes(b"yesterday's timetable")
    calls = []
    monkeypatch.setattr(dashboard_module, "build_departures", fake_build(calls))
    dashboard = make_dashboard(tmp_path, client=FakeGrandLyon(gtfs=down))

    dashboard.refresh_timetable(date(2026, 10, 16))

    assert len(calls) == 1
    assert dashboard.scheduled_for == date(2026, 10, 16)


def test_refresh_timetable_fails_without_any_timetable(tmp_path):
    dashboard = make_dashboard(tmp_path, client=FakeGrandLyon(gtfs=down))

    with pytest.raises(requests.ConnectionError):
        dashboard.refresh_timetable(date(2026, 10, 16))


def test_load_downloads_everything_and_orders_the_stops(monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard_module, "build_departures", fake_build([]))
    monkeypatch.setattr(
        dashboard_module,
        "stop_orders",
        lambda path, lines: {("T2", "A"): ["33685", "32103"]},
    )
    monkeypatch.setattr(dashboard_module, "load_geometry", lambda client: ({}, {}))
    client = FakeGrandLyon(wfs=fake_fetch_wfs)

    dashboard = Dashboard.load(client, tmp_path)

    assert set(dashboard.platforms) == {"32103"}
    assert dashboard.lines["T2"].stops == {"A": ["33685", "32103"]}
    assert dashboard.lines["C9"].stops == {}
    assert dashboard.scheduled_for == date.today()
    assert client.pictos_dir == tmp_path / "pictos"


# ---------------------------------------------------------------- live data

NOW = datetime(2099, 1, 1, 8, 0)
FAKE_FAVOURITES = [
    Favourite(line="T2", sens="A", platform="32103"),
    Favourite(line="C9", sens="A", platform="33685"),
]
FAKE_PASSAGES = [
    {
        "id": "32103",
        "ligne": "T2",
        "heurepassage": "2099-01-01 08:05:00",
        "type": "E",
        "coursetheorique": "trip-t2",
        "last_update_fme": "2099-01-01 08:00:00",
    },
    {
        "id": "33685",
        "ligne": "C9",
        "heurepassage": "2099-01-01 08:10:00",
        "type": "T",
        "coursetheorique": "trip-c9",
        "last_update_fme": "2099-01-01 08:00:00",
    },
]
T2_AT_PERRACHE = Departure("T2", "32103", datetime(2099, 1, 1, 8, 5), realtime=True)
C9_AT_BELLECOUR = Departure("C9", "33685", datetime(2099, 1, 1, 8, 10), realtime=False)


class CountingPassages:
    """fetch_passages answers: notes each call, fails from call `fail_from` on."""

    def __init__(self, fail_from=None):
        self.calls = []
        self.fail_from = fail_from

    def __call__(self, platform_ids):
        self.calls.append(platform_ids)
        if self.fail_from is not None and len(self.calls) >= self.fail_from:
            raise requests.ConnectionError()
        return FAKE_PASSAGES


def live_dashboard(tmp_path, passages=None, alerts=None, **kwargs):
    """A dashboard with the two favourites, whose timetable is already built
    for NOW (so it never reads a GTFS file)."""
    client = FakeGrandLyon(passages=passages or CountingPassages(), alerts=alerts)
    dashboard = make_dashboard(
        tmp_path, client=client, favourites=FAKE_FAVOURITES, **kwargs
    )
    dashboard.scheduled_for = NOW.date()
    return dashboard


def test_board_has_one_card_per_favourite(tmp_path):
    passages = CountingPassages()
    board = live_dashboard(tmp_path, passages).board(NOW)

    assert board.cards == [
        Card(
            line="T2",
            sens="A",
            platform="32103",
            colour="#6BA230",
            platform_name="Perrache",
            destination="Saint-Priest Bel Air",
            departures=[T2_AT_PERRACHE],
            disrupted=False,
        ),
        Card(
            line="C9",
            sens="A",
            platform="33685",
            colour="#C88817",
            platform_name="Bellecour A. Poncet",
            destination="Hopitaux Est",
            departures=[C9_AT_BELLECOUR],
            disrupted=False,
        ),
    ]
    assert board.banner is None
    assert board.stale is False
    assert board.updated_at == NOW
    assert passages.calls == [["32103", "33685"]]


def test_board_uses_the_timetable_for_the_metro(tmp_path):
    platforms = {
        "30101": Platform(id="30101", name="Perrache", line_directions={("A", "A")})
    }
    lines = {"A": Line("A", "MET", "#E8308A", {"A": "Vaulx-en-Velin La Soie"})}
    scheduled = Departure("A", "30101", datetime(2099, 1, 1, 8, 5), realtime=False)

    def no_realtime(platform_ids):
        raise AssertionError("the metro must not ask for real-time data")

    dashboard = make_dashboard(
        tmp_path,
        lines=lines,
        platforms=platforms,
        client=FakeGrandLyon(passages=no_realtime),
        favourites=[Favourite(line="A", sens="A", platform="30101")],
    )
    dashboard.scheduled = [scheduled]
    dashboard.scheduled_for = NOW.date()

    assert dashboard.board(NOW).cards[0].departures == [scheduled]


def test_board_reuses_recent_passages(tmp_path):
    passages = CountingPassages()
    dashboard = live_dashboard(tmp_path, passages)

    dashboard.board(NOW)
    dashboard.board(NOW + timedelta(seconds=10))
    assert len(passages.calls) == 1

    dashboard.board(NOW + timedelta(minutes=1))
    assert len(passages.calls) == 2


def test_board_serves_stale_data_when_grand_lyon_is_down(tmp_path):
    dashboard = live_dashboard(tmp_path, CountingPassages(fail_from=2))

    dashboard.board(NOW)  # Grand Lyon answers
    board = dashboard.board(NOW + timedelta(minutes=1))  # Grand Lyon is down

    assert board.stale is True
    assert board.updated_at == NOW  # the last good passages
    assert [card.departures for card in board.cards] == [
        [T2_AT_PERRACHE],
        [C9_AT_BELLECOUR],
    ]


def test_stop_detail_shows_departures_and_next_stops(tmp_path):
    lines = {
        "T2": Line(
            "T2",
            "TRA",
            "#6BA230",
            {"A": "Saint-Priest Bel Air"},
            stops={"A": ["32103", "33685"]},
        ),
        "C9": FAKE_LINES["C9"],
    }
    passages = CountingPassages()
    dashboard = live_dashboard(tmp_path, passages, lines=lines)
    dashboard.set_favourites([Favourite(line="C9", sens="A", platform="33685")])

    detail = dashboard.stop_detail("32103", "T2", "A", NOW)

    assert detail.departures == [T2_AT_PERRACHE]
    assert detail.next_stops == ["Perrache", "Bellecour A. Poncet"]
    assert detail.remaining == 0
    assert detail.favourite is False
    assert detail.stale is False
    # the board's favourite platform is fetched too, to keep the shared cache
    assert passages.calls == [["33685", "32103"]]


def test_stop_detail_refuses_an_unknown_stop(tmp_path):
    with pytest.raises(NotFound):
        live_dashboard(tmp_path).stop_detail("32103", "T2", "R", NOW)


def alert_row(line, severity, title):
    return {
        "ligne_cli": line,
        "type": "Perturbation",
        "niveauseverite": severity,
        "debut": "2026-01-01 00:00:00",
        "fin": "2099-12-31 00:00:00",
        "titre": title,
        "message": "",
    }


def test_alerts_page_splits_my_lines_from_the_network(tmp_path):
    rows = [
        alert_row("B", 30, "Info B"),
        alert_row("T2", 30, "Info T2"),
        alert_row("T2", 20, "Travaux T2"),
    ]
    page = live_dashboard(tmp_path, alerts=lambda: rows).alerts_page(NOW)

    assert [alert.title for alert in page.mine] == ["Travaux T2", "Info T2"]
    assert [alert.title for alert in page.network] == [
        "Travaux T2",
        "Info B",
        "Info T2",
    ]
    assert all(isinstance(alert, Alert) for alert in page.network)
    assert page.updated_at == NOW
    assert page.stale is False


def test_set_favourites_saves_and_uses_them(tmp_path):
    dashboard = make_dashboard(tmp_path)
    favourites = [Favourite(line="T2", sens="A", platform="32103")]

    dashboard.set_favourites(favourites)

    assert dashboard.favourites == favourites
    assert load_favourites(tmp_path / "favourites.json") == favourites


def test_set_favourites_refuses_invalid_ones_and_keeps_the_old(tmp_path):
    old = [Favourite(line="T2", sens="A", platform="32103")]
    dashboard = make_dashboard(tmp_path, favourites=old)

    with pytest.raises(InvalidFavourites) as refused:
        dashboard.set_favourites([Favourite(line="ZZZ", sens="A", platform="32103")])

    assert refused.value.args[0] == ["unknown line ZZZ"]
    assert dashboard.favourites == old
    assert load_favourites(tmp_path / "favourites.json") == old
