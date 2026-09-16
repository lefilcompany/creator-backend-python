from __future__ import annotations

from collections import defaultdict
from threading import Lock


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


class MetricsRegistry:
    """Small Prometheus exposition registry with intentionally bounded labels."""

    def __init__(self) -> None:
        self._counters: dict[tuple[str, str, str], int] = defaultdict(int)
        self._lock = Lock()

    def increment(self, *, rate_class: str, endpoint: str, outcome: str) -> None:
        with self._lock:
            self._counters[(rate_class, endpoint, outcome)] += 1

    def render(self) -> str:
        with self._lock:
            counters = sorted(self._counters.items())

        lines = [
            "# HELP creator_rate_limit_requests_total Rate limiter decisions.",
            "# TYPE creator_rate_limit_requests_total counter",
        ]
        for (rate_class, endpoint, outcome), value in counters:
            lines.append(
                "creator_rate_limit_requests_total{"
                f'class="{_escape_label(rate_class)}",'
                f'endpoint="{_escape_label(endpoint)}",'
                f'outcome="{_escape_label(outcome)}"}} {value}'
            )
        return "\n".join(lines) + "\n"

    @property
    def content_type(self) -> str:
        return "text/plain; version=0.0.4; charset=utf-8"
