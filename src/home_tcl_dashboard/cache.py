from collections.abc import Callable
from datetime import datetime
from typing import Any

import requests


class LastGood:
    """Remembers the last succesful fetch, to serve it when the source fails."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.fetched_at: datetime | None = None

    def refresh(self, fetch: Callable[[], list[dict[str, Any]]], now: datetime) -> bool:
        """Try fetch; keep the previous rows if it fails. Return True if stale."""
        try:
            rows = fetch()
        except requests.RequestException:
            return True

        self.rows = rows
        self.fetched_at = now

        return False
