from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from typing import Any

import requests


class LastGood:
    """Remembers the last succesful fetch: reuses it while it is younger than
    `max_age`, and serves it when the source fails."""

    def __init__(self, max_age: timedelta) -> None:
        self.max_age = max_age
        self.rows: list[dict[str, Any]] = []
        self.fetched_at: datetime | None = None
        self.keys: frozenset[str] = frozenset()  # what the rows were fetched for

    def refresh(
        self,
        fetch: Callable[[], list[dict[str, Any]]],
        now: datetime,
        keys: Iterable[str] = (),
    ) -> bool:
        """Fetch unless the rows are recent and cover `keys` (e.g. platform ids);
        keep the previous rows if it fails. Return True if stale."""
        wanted = frozenset(keys)
        if (
            self.fetched_at is not None
            and now - self.fetched_at < self.max_age
            and wanted <= self.keys
        ):
            return False
        try:
            rows = fetch()
        except requests.RequestException:
            return True

        self.rows = rows
        self.fetched_at = now
        self.keys = wanted

        return False
