from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class LicenseCheckResult:
    ok: bool
    error_code: str | None = None
    message: str = ""
    payload: dict[str, Any] | None = None
    envelope: dict[str, Any] | None = None

