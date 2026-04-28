from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LicenseStorage:
    def __init__(self, license_path: Path | None = None) -> None:
        default_path = Path.home() / ".bibtex_mvp" / "license.json"
        self.license_path = license_path or default_path

    def exists(self) -> bool:
        return self.license_path.exists()

    def read_text(self) -> str:
        return self.license_path.read_text(encoding="utf-8")

    def write_envelope(self, envelope: dict[str, Any]) -> None:
        self.license_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.license_path.with_suffix(".json.tmp")
        data = json.dumps(envelope, ensure_ascii=False, indent=2)
        temp_path.write_text(data, encoding="utf-8")
        temp_path.replace(self.license_path)

