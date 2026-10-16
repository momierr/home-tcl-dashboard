from datetime import datetime, timedelta
from typing import Any

import requests

from home_tcl_dashboard.cache import LastGood

EARLIER = datetime(2026, 10, 16, 8, 0)
NOW = datetime(2026, 10, 16, 8, 1)
MAX_AGE = timedelta(seconds=30)


def broken() -> list[dict[str, Any]]:
    raise requests.ConnectionError()


def test_refresh_keeps_fresh_rows() -> None:
    cache = LastGood(MAX_AGE)

    stale = cache.refresh(lambda: [{"id": "1"}], NOW)

    assert stale is False
    assert cache.rows == [{"id": "1"}]
    assert cache.fetched_at == NOW


def test_refresh_keeps_previous_rows_when_the_source_fails() -> None:
    cache = LastGood(MAX_AGE)
    cache.refresh(lambda: [{"id": "1"}], EARLIER)

    stale = cache.refresh(broken, NOW)

    assert stale is True
    assert cache.rows == [{"id": "1"}]
    assert cache.fetched_at == EARLIER


def test_refresh_is_stale_and_empty_when_the_first_fetch_fails() -> None:
    cache = LastGood(MAX_AGE)

    stale = cache.refresh(broken, NOW)

    assert stale is True
    assert cache.rows == []
    assert cache.fetched_at is None


def test_refresh_reuses_recent_rows_without_fetching() -> None:
    cache = LastGood(MAX_AGE)
    cache.refresh(lambda: [{"id": "1"}], EARLIER)

    stale = cache.refresh(broken, EARLIER + timedelta(seconds=10))

    assert stale is False
    assert cache.rows == [{"id": "1"}]
    assert cache.fetched_at == EARLIER


def test_refresh_fetches_again_when_rows_are_too_old() -> None:
    cache = LastGood(MAX_AGE)
    cache.refresh(lambda: [{"id": "1"}], EARLIER)

    cache.refresh(lambda: [{"id": "2"}], EARLIER + MAX_AGE)

    assert cache.rows == [{"id": "2"}]


def test_refresh_reuses_rows_that_cover_the_keys() -> None:
    cache = LastGood(MAX_AGE)
    cache.refresh(lambda: [{"id": "1"}], EARLIER, ["32103", "30101"])

    cache.refresh(broken, EARLIER, ["32103"])

    assert cache.rows == [{"id": "1"}]


def test_refresh_fetches_again_for_a_new_key() -> None:
    cache = LastGood(MAX_AGE)
    cache.refresh(lambda: [{"id": "1"}], EARLIER, ["32103"])

    cache.refresh(lambda: [{"id": "2"}], EARLIER, ["32103", "10515"])

    assert cache.rows == [{"id": "2"}]
    assert cache.keys == {"32103", "10515"}
