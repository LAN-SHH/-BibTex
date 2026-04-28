from __future__ import annotations

import json
from typing import Any


def canonical_json_bytes(payload: Any) -> bytes:
    """
    Deterministic JSON canonicalization for license payload signing/verification.
    - UTF-8
    - sorted keys
    - no extra whitespace
    - fixed separators
    - unicode kept as-is
    """
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return canonical.encode("utf-8")

