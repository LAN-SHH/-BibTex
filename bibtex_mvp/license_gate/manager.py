from __future__ import annotations

from pathlib import Path
from typing import Any

from . import error_codes as codes
from .device_id import get_device_id
from .models import LicenseCheckResult
from .public_key import APP_PUBLIC_KEY_BASE64
from .storage import LicenseStorage
from .verifier import LicenseVerifier


class LicenseManager:
    def __init__(
        self,
        storage: LicenseStorage | None = None,
        verifier: LicenseVerifier | None = None,
        device_id_provider=None,
    ) -> None:
        self.storage = storage or LicenseStorage()
        self.verifier = verifier or LicenseVerifier(
            public_key_base64=APP_PUBLIC_KEY_BASE64,
            supported_versions={"1"},
        )
        self._device_id_provider = device_id_provider or get_device_id

    def validate_local_license(self) -> LicenseCheckResult:
        if not self.storage.exists():
            return LicenseCheckResult(ok=False, error_code=codes.LICENSE_NOT_FOUND, message="未找到本地许可证")
        try:
            text = self.storage.read_text()
        except UnicodeDecodeError:
            return LicenseCheckResult(ok=False, error_code=codes.CORRUPTED_LICENSE, message="许可证文件编码损坏")
        except OSError:
            return LicenseCheckResult(ok=False, error_code=codes.CORRUPTED_LICENSE, message="许可证文件读取失败")

        result = self.verifier.verify_license_text(text)
        if not result.ok:
            return result
        return self._bind_device_if_needed(result, persist=True)

    def validate_and_store(self, license_text: str) -> LicenseCheckResult:
        result = self.verifier.verify_license_text(license_text)
        if not result.ok:
            return result
        result = self._bind_device_if_needed(result, persist=False)
        if not result.ok or result.envelope is None:
            return result
        self.storage.write_envelope(result.envelope)
        return result

    @property
    def license_path(self) -> Path:
        return self.storage.license_path

    def _bind_device_if_needed(self, result: LicenseCheckResult, *, persist: bool) -> LicenseCheckResult:
        envelope = result.envelope
        payload = result.payload
        if not isinstance(envelope, dict) or not isinstance(payload, dict):
            return LicenseCheckResult(ok=False, error_code=codes.CORRUPTED_LICENSE, message="许可证结构损坏")

        bind_to_device = payload.get("bind_to_device")
        if bind_to_device is not True:
            return result

        payload_device_id = payload.get("device_id")
        if isinstance(payload_device_id, str) and payload_device_id.strip():
            return result

        activated_device_id = envelope.get("activated_device_id")
        if isinstance(activated_device_id, str) and activated_device_id.strip():
            return result

        current_device_id = self._device_id_provider()
        if not current_device_id:
            return LicenseCheckResult(
                ok=False,
                error_code=codes.DEVICE_ID_UNAVAILABLE,
                message="无法获取本机设备标识",
            )

        # Keep signed payload unchanged; store runtime binding in envelope top-level.
        updated_envelope: dict[str, Any] = dict(envelope)
        updated_envelope["activated_device_id"] = current_device_id
        if persist:
            self.storage.write_envelope(updated_envelope)
        return LicenseCheckResult(
            ok=True,
            message="许可证校验通过",
            payload=payload,
            envelope=updated_envelope,
        )
