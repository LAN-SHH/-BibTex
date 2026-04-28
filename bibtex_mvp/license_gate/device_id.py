from __future__ import annotations

import subprocess
import uuid


def get_device_id() -> str | None:
    """
    Try stable device id on Windows first, then fallback to MAC node.
    Returns None when a reliable identifier cannot be obtained.
    """
    machine_guid = _read_windows_machine_guid()
    if machine_guid:
        return machine_guid

    node = uuid.getnode()
    if node is None or node == 0:
        return None
    return f"mac-{node:012x}"


def _read_windows_machine_guid() -> str | None:
    try:
        cmd = (
            "Get-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Cryptography' "
            "-Name MachineGuid | Select-Object -ExpandProperty MachineGuid"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    value = (proc.stdout or "").strip()
    return value or None

