from datetime import datetime
from typing import Any

import requests

from home_tcl_dashboard.cache import LastGood

EARLIER = datetime(2026, 10, 16, 8, 0)
NOW = datetime(2026, 10, 16, 8, 1)


def broken() -> list[dict[str, Any]]:
    raise requests.ConnectionError()


def test_refresh_keeps_fresh_rows() -> None:
    cache = LastGood()

    stale = cache.refresh(lambda: [{"id": "1"}], NOW)

    assert stale is False
    assert cache.rows == [{"id": "1"}]
    assert cache.fetched_at == NOW


def test_refresh_keeps_previous_rows_when_the_source_fails() -> None:
    cache = LastGood()
    cache.refresh(lambda: [{"id": "1"}], EARLIER)

    stale = cache.refresh(broken, NOW)

    assert stale is True
    assert cache.rows == [{"id": "1"}]
    assert cache.fetched_at == EARLIER


def test_refresh_is_stale_and_empty_when_the_first_fetch_fails() -> None:
    cache = LastGood()

    stale = cache.refresh(broken, NOW)

    assert stale is True
    assert cache.rows == []
    assert cache.fetched_at is None
