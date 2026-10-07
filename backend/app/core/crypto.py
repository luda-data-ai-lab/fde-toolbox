"""Symmetric encryption for per-tenant secrets (adapter credentials) keyed by ENCRYPTION_KEY."""

import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class DecryptionError(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = get_settings().encryption_key
    try:
        return Fernet(key)
    except ValueError:
        return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))


def encrypt_json(value: dict[str, str]) -> str:
    return _fernet().encrypt(json.dumps(value).encode()).decode()


def decrypt_json(token: str) -> dict[str, str]:
    try:
        data = json.loads(_fernet().decrypt(token.encode()))
    except (InvalidToken, ValueError) as exc:
        raise DecryptionError("cannot decrypt credentials") from exc
    if not isinstance(data, dict):
        raise DecryptionError("credentials are not an object")
    return {str(k): str(v) for k, v in data.items()}
