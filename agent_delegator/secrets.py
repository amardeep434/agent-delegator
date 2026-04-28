"""Secure storage for sensitive configuration values using Fernet encryption."""

import base64
import hashlib
import json
import os
import warnings
from pathlib import Path

try:
    from cryptography.fernet import Fernet
except ImportError:  # pragma: no cover
    Fernet = None


def _derive_key() -> bytes:
    """Derive a stable encryption key from machine-specific state.

    The key is bound to the current machine and user account so that
    an attacker who gains access to the encrypted file cannot decrypt it
    on a different machine.  It is *not* a password — the goal is to
    protect data at rest from casual inspection, not to resist a
    determined adversary with root access.
    """
    # Mix several stable, machine-specific values into a 32-byte key.
    salt = b"delegator-v1"
    machine_id = hashlib.sha256(
        f"{os.uname().nodename}:{os.getuid()}:{Path.home()}".encode()
    ).digest()
    return base64.urlsafe_b64encode(hashlib.pbkdf2_hmac("sha256", machine_id, salt, 100000, dklen=32))


def _get_fernet() -> Fernet | None:
    if Fernet is None:
        warnings.warn(
            "cryptography is not installed. Sensitive config values will be stored in plaintext. "
            "Install it with: pip install cryptography",
            RuntimeWarning,
            stacklevel=3,
        )
        return None
    return Fernet(_derive_key())


def _is_encrypted(value: str) -> bool:
    """Heuristic: Fernet tokens are base64url strings ending with '='."""
    if not isinstance(value, str) or len(value) < 20:
        return False
    try:
        # Quick check: Fernet tokens start with a version byte (0x80 = 'g')
        # and contain only base64url chars
        return value.startswith("g") and value.rstrip("=").replace("-", "").replace("_", "").isalnum()
    except Exception:
        return False


_ENCRYPTED_KEYS = {"bot_token", "chat_id", "slack_url"}


def encrypt_config(cfg: dict) -> dict:
    """Encrypt sensitive fields in a notification config dict."""
    f = _get_fernet()
    if f is None:
        return cfg

    out = {}
    for section, values in cfg.items():
        if not isinstance(values, dict):
            out[section] = values
            continue
        sec = {}
        for key, value in values.items():
            if key in _ENCRYPTED_KEYS and isinstance(value, str) and value and not _is_encrypted(value):
                sec[key] = f.encrypt(value.encode()).decode()
            else:
                sec[key] = value
        out[section] = sec
    return out


def decrypt_config(cfg: dict) -> dict:
    """Decrypt sensitive fields in a notification config dict."""
    f = _get_fernet()
    if f is None:
        return cfg

    out = {}
    for section, values in cfg.items():
        if not isinstance(values, dict):
            out[section] = values
            continue
        sec = {}
        for key, value in values.items():
            if key in _ENCRYPTED_KEYS and isinstance(value, str) and _is_encrypted(value):
                try:
                    sec[key] = f.decrypt(value.encode()).decode()
                except Exception:
                    # If decryption fails (e.g. machine changed), leave as-is
                    sec[key] = value
            else:
                sec[key] = value
        out[section] = sec
    return out
