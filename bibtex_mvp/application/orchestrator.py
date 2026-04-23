from __future__ import annotations

from dataclasses import dataclass
from threading import Event


@dataclass(slots=True)
class ResolverConfig:
    auto_accept_threshold: float = 0.92
    candidate_floor_threshold: float = 0.80
    max_rows: int = 20
    search_timeout_sec: float = 6.0
    batch_concurrency: int = 3


class BatchCancelToken:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()
