from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone

from nacl.signing import SigningKey

from bibtex_mvp.license_gate import error_codes as codes
from bibtex_mvp.license_gate.canonical_json import canonical_json_bytes
from bibtex_mvp.license_gate.manager import LicenseManager
from bibtex_mvp.license_gate.storage import LicenseStorage
from bibtex_mvp.license_gate.verifier import LicenseVerifier


def _future_time() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=30)).replace(microsecond=0).isoformat()


def _past_time() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).replace(microsecond=0).isoformat()


def _make_envelope(
    signing_key: SigningKey,
    payload: dict,
    version: str = "1",
) -> dict:
    payload_bytes = canonical_json_bytes(payload)
    signature = signing_key.sign(payload_bytes).signature
    return {
        "version": version,
        "payload": payload,
        "signature": base64.b64encode(signature).decode("ascii"),
    }


def _verifier(signing_key: SigningKey, device_id_provider=None) -> LicenseVerifier:
    verify_key_b64 = base64.b64encode(signing_key.verify_key.encode()).decode("ascii")
    return LicenseVerifier(
        public_key_base64=verify_key_b64,
        supported_versions={"1"},
        device_id_provider=device_id_provider,
    )


def test_canonical_json_is_deterministic_for_key_order() -> None:
    a = {"b": 1, "a": {"z": 2, "x": 3}}
    b = {"a": {"x": 3, "z": 2}, "b": 1}
    assert canonical_json_bytes(a) == canonical_json_bytes(b)


def test_bind_false_allows_empty_device_id() -> None:
    sk = SigningKey.generate()
    verifier = _verifier(sk, device_id_provider=lambda: "other-device")
    payload = {
        "license_id": "L-001",
        "expires_at": _future_time(),
        "bind_to_device": False,
        "device_id": "",
    }
    result = verifier.verify_envelope(_make_envelope(sk, payload))
    assert result.ok is True


def test_bind_true_device_id_unavailable() -> None:
    sk = SigningKey.generate()
    verifier = _verifier(sk, device_id_provider=lambda: None)
    payload = {
        "license_id": "L-002",
        "expires_at": _future_time(),
        "bind_to_device": True,
        "device_id": "machine-001",
    }
    result = verifier.verify_envelope(_make_envelope(sk, payload))
    assert result.ok is False
    assert result.error_code == codes.DEVICE_ID_UNAVAILABLE


def test_bind_true_device_mismatch() -> None:
    sk = SigningKey.generate()
    verifier = _verifier(sk, device_id_provider=lambda: "machine-002")
    payload = {
        "license_id": "L-003",
        "expires_at": _future_time(),
        "bind_to_device": True,
        "device_id": "machine-001",
    }
    result = verifier.verify_envelope(_make_envelope(sk, payload))
    assert result.ok is False
    assert result.error_code == codes.DEVICE_MISMATCH


def test_unsupported_version() -> None:
    sk = SigningKey.generate()
    verifier = _verifier(sk)
    payload = {
        "license_id": "L-004",
        "expires_at": _future_time(),
        "bind_to_device": False,
        "device_id": "",
    }
    result = verifier.verify_envelope(_make_envelope(sk, payload, version="9"))
    assert result.ok is False
    assert result.error_code == codes.UNSUPPORTED_VERSION


def test_invalid_signature() -> None:
    sk1 = SigningKey.generate()
    sk2 = SigningKey.generate()
    verifier = _verifier(sk1)
    payload = {
        "license_id": "L-005",
        "expires_at": _future_time(),
        "bind_to_device": False,
        "device_id": "",
    }
    envelope = _make_envelope(sk2, payload)
    result = verifier.verify_envelope(envelope)
    assert result.ok is False
    assert result.error_code == codes.INVALID_SIGNATURE


def test_expired_license() -> None:
    sk = SigningKey.generate()
    verifier = _verifier(sk)
    payload = {
        "license_id": "L-006",
        "expires_at": _past_time(),
        "bind_to_device": False,
        "device_id": "",
    }
    result = verifier.verify_envelope(_make_envelope(sk, payload))
    assert result.ok is False
    assert result.error_code == codes.EXPIRED


def test_manager_overwrites_old_license(tmp_path) -> None:
    sk = SigningKey.generate()
    verify_key_b64 = base64.b64encode(sk.verify_key.encode()).decode("ascii")
    storage = LicenseStorage(tmp_path / "license.json")
    manager = LicenseManager(
        storage=storage,
        verifier=LicenseVerifier(
            public_key_base64=verify_key_b64,
            supported_versions={"1"},
            device_id_provider=lambda: "machine-001",
        ),
        device_id_provider=lambda: "machine-001",
    )

    old_payload = {
        "license_id": "OLD",
        "expires_at": _future_time(),
        "bind_to_device": False,
        "device_id": "",
    }
    new_payload = {
        "license_id": "NEW",
        "expires_at": _future_time(),
        "bind_to_device": False,
        "device_id": "",
    }
    old_text = json.dumps(_make_envelope(sk, old_payload), ensure_ascii=False)
    new_text = json.dumps(_make_envelope(sk, new_payload), ensure_ascii=False)

    assert manager.validate_and_store(old_text).ok is True
    assert manager.validate_and_store(new_text).ok is True

    persisted = json.loads(storage.read_text())
    assert persisted["payload"]["license_id"] == "NEW"


def test_manager_local_license_not_found(tmp_path) -> None:
    sk = SigningKey.generate()
    verify_key_b64 = base64.b64encode(sk.verify_key.encode()).decode("ascii")
    storage = LicenseStorage(tmp_path / "missing.json")
    manager = LicenseManager(
        storage=storage,
        verifier=LicenseVerifier(
            public_key_base64=verify_key_b64,
            supported_versions={"1"},
            device_id_provider=lambda: "machine-001",
        ),
        device_id_provider=lambda: "machine-001",
    )
    result = manager.validate_local_license()
    assert result.ok is False
    assert result.error_code == codes.LICENSE_NOT_FOUND


def test_bind_true_empty_device_id_auto_bind_on_store(tmp_path) -> None:
    sk = SigningKey.generate()
    verify_key_b64 = base64.b64encode(sk.verify_key.encode()).decode("ascii")
    storage = LicenseStorage(tmp_path / "license.json")
    manager = LicenseManager(
        storage=storage,
        verifier=LicenseVerifier(
            public_key_base64=verify_key_b64,
            supported_versions={"1"},
            device_id_provider=lambda: "machine-001",
        ),
        device_id_provider=lambda: "machine-001",
    )
    payload = {
        "license_id": "AUTO-BIND-1",
        "expires_at": _future_time(),
        "bind_to_device": True,
        "device_id": "",
    }
    text = json.dumps(_make_envelope(sk, payload), ensure_ascii=False)
    result = manager.validate_and_store(text)
    assert result.ok is True
    persisted = json.loads(storage.read_text())
    assert persisted.get("activated_device_id") == "machine-001"


def test_bind_true_activated_device_id_mismatch() -> None:
    sk = SigningKey.generate()
    verify_key_b64 = base64.b64encode(sk.verify_key.encode()).decode("ascii")
    verifier = LicenseVerifier(
        public_key_base64=verify_key_b64,
        supported_versions={"1"},
        device_id_provider=lambda: "machine-002",
    )
    payload = {
        "license_id": "AUTO-BIND-2",
        "expires_at": _future_time(),
        "bind_to_device": True,
        "device_id": "",
    }
    envelope = _make_envelope(sk, payload)
    envelope["activated_device_id"] = "machine-001"
    result = verifier.verify_envelope(envelope)
    assert result.ok is False
    assert result.error_code == codes.DEVICE_MISMATCH
