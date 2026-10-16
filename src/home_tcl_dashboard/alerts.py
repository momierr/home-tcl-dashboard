from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class Alert:
    line: str
    kind: str
    severity: int
    start: datetime
    end: datetime
    title: str
    message: str


def parse_alert(row: dict[str, Any]) -> Alert:
    """One raw traffic alert -> Alert (a lower severity is more serious)."""
    return Alert(
        line=row["ligne_cli"],
        kind=row["type"],
        severity=row["niveauseverite"],
        start=datetime.fromisoformat(row["debut"]),
        end=datetime.fromisoformat(row["fin"]),
        title=row["titre"],
        message=row["message"],
    )


def active_alerts(alerts: list[Alert], now: datetime) -> list[Alert]:
    return [alert for alert in alerts if alert.start <= now <= alert.end]
