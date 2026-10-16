from typing import Any


def latest_estimates(passages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for passage in passages:
        trip = passage["coursetheorique"]
        if (
            trip not in latest
            or passage["last_update_fme"] > latest[trip]["last_update_fme"]
        ):
            latest[trip] = passage

    return list(latest.values())
