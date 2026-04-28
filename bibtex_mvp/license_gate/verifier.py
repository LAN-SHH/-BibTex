from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any, Callable

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from .canonical_json import canonical_json_bytes
from . import error_codes as codes
from .messages import ERROR_MESSAGES_ZH
from .models import LicenseCheckResult


class LicenseVerifier:
    def __init__(
        self,
        public_key_base64: str,
        supported_versions: set[str] | None = None,
        device_id_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self._public_key_base64 = public_key_base64
        self._supported_versions = supported_versions or {"1"}
        from .device_id import get_device_id

        self._device_id_provider = device_id_provider or get_device_id

    def verify_license_text(self, license_text: str) -> LicenseCheckResult:
        try:
            envelope = json.loads(license_text)
        except json.JSONDecodeError:
            return self._error(codes.INVALID_JSON)
        return self.verify_envelope(envelope)

    def verify_envelope(self, envelope: Any) -> LicenseCheckResult:
        if not isinstance(envelope, dict):
            return self._error(codes.CORRUPTED_LICENSE)

        if "version" not in envelope or "payload" not in envelope or "signature" not in envelope:
            return self._error(codes.CORRUPTED_LICENSE)

        version = str(envelope.get("version"))
        if version not in self._supported_versions:
            return self._error(codes.UNSUPPORTED_VERSION)

        payload = envelope.get("payload")
        signature = envelope.get("signature")
        if not isinstance(payload, dict) or not isinstance(signature, str):
            return self._error(codes.CORRUPTED_LICENSE)

        if not self._verify_signature(payload, signature):
            return self._error(codes.INVALID_SIGNATURE)

        expires_at = payload.get("expires_at")
        if not isinstance(expires_at, str):
            return self._error(codes.CORRUPTED_LICENSE)
        if self._is_expired(expires_at):
            return self._error(codes.EXPIRED)

        bind_to_device = payload.get("bind_to_device")
        if not isinstance(bind_to_device, bool):
            return self._error(codes.CORRUPTED_LICENSE)

        # bind_to_device is false: skip device_id validation entirely.
        if bind_to_device:
            current_device_id = self._device_id_provider()
            if not current_device_id:
                return self._error(codes.DEVICE_ID_UNAVAILABLE)
            expected_from_payload = payload.get("device_id")
            expected_from_envelope = envelope.get("activated_device_id")
            expected_device_id = ""
            if isinstance(expected_from_payload, str) and expected_from_payload.strip():
                expected_device_id = expected_from_payload.strip()
            elif isinstance(expected_from_envelope, str) and expected_from_envelope.strip():
                expected_device_id = expected_from_envelope.strip()
            if expected_device_id and current_device_id != expected_device_id:
                return self._error(codes.DEVICE_MISMATCH)

        return LicenseCheckResult(
            ok=True,
            message="许可证校验通过",
            payload=payload,
            envelope=envelope,
        )

    def _verify_signature(self, payload: dict[str, Any], signature_b64: str) -> bool:
        try:
            verify_key_bytes = base64.b64decode(self._public_key_base64, validate=True)
            signature_bytes = base64.b64decode(signature_b64, validate=True)
            payload_bytes = canonical_json_bytes(payload)
            verify_key = VerifyKey(verify_key_bytes)
            verify_key.verify(payload_bytes, signature_bytes)
            return True
        except (ValueError, BadSignatureError):
            return False
        except Exception:
            return False

    def _is_expired(self, expires_at: str) -> bool:
        try:
            normalized = expires_at.replace("Z", "+00:00")
            expiry = datetime.fromisoformat(normalized)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            return now_utc > expiry
        except ValueError:
            return True

    def _error(self, error_code: str) -> LicenseCheckResult:
        return LicenseCheckResult(
            ok=False,
            error_code=error_code,
            message=ERROR_MESSAGES_ZH.get(error_code, error_code),
        )
