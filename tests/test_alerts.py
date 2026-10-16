from dataclasses import replace
from datetime import datetime
from typing import Any

from home_tcl_dashboard.alerts import Alert, active_alerts, parse_alert


def test_parse_alert() -> None:
    row = {
        "ligne_cli": "D",
        "ligne_com": "D",
        "type": "Perturbation",
        "niveauseverite": 20,
        "debut": "2026-10-05 21:20:00",
        "fin": "2026-11-25 01:30:00",
        "titre": "Travaux modernisation ligne D",
        "message": "Circulation partielle les lundis et mardis.",
    }

    assert parse_alert(row) == Alert(
        line="D",
        kind="Perturbation",
        severity=20,
        start=datetime(2026, 10, 5, 21, 20),
        end=datetime(2026, 11, 25, 1, 30),
        title="Travaux modernisation ligne D",
        message="Circulation partielle les lundis et mardis.",
    )


NOW = datetime(2026, 10, 15, 12, 0)


def dummy_alert(**fields: Any) -> Alert:
    alert = Alert(
        line="D",
        kind="Perturbation",
        severity=20,
        start=datetime(2026, 10, 1),
        end=datetime(2026, 10, 31),
        title="Travaux",
        message="Circulation partielle.",
    )
    return replace(alert, **fields)


def test_active_alerts_keeps_a_current_alert() -> None:
    current = dummy_alert()

    assert active_alerts([current], NOW) == [current]


def test_active_alerts_skips_a_future_alert() -> None:
    future = dummy_alert(start=datetime(2026, 10, 20))

    assert active_alerts([future], NOW) == []


def test_active_alerts_skips_an_expired_alert() -> None:
    expired = dummy_alert(end=datetime(2026, 10, 10))

    assert active_alerts([expired], NOW) == []


def test_active_alerts_keeps_an_alert_starting_now() -> None:
    starting = dummy_alert(start=NOW)

    assert active_alerts([starting], NOW) == [starting]
