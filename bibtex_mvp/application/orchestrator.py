from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ResolverConfig:
    auto_accept_threshold: float = 0.92
    candidate_floor_threshold: float = 0.80
    max_rows: int = 20

