from datetime import datetime

from home_tcl_dashboard.alerts import Alert, parse_alert


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
