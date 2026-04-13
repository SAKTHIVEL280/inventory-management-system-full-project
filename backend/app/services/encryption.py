"""Field-level encryption helpers for sensitive columns."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.config import settings


def _build_fernet() -> Fernet:
    # Derive a stable Fernet key from SECRET_KEY.
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


_FERNET = _build_fernet()
_ENCRYPTED_PREFIX = "enc:"


class EncryptedString(TypeDecorator):
    """Encrypt values before persistence and decrypt on read.

    Plain legacy values are returned as-is to remain backward compatible.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value

        raw = str(value)
        if not raw:
            return raw
        if raw.startswith(_ENCRYPTED_PREFIX):
            return raw

        token = _FERNET.encrypt(raw.encode("utf-8")).decode("utf-8")
        return f"{_ENCRYPTED_PREFIX}{token}"

    def process_result_value(self, value, dialect):
        if value is None:
            return value

        raw = str(value)
        if not raw.startswith(_ENCRYPTED_PREFIX):
            return raw

        token = raw[len(_ENCRYPTED_PREFIX) :]
        try:
            return _FERNET.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            # Keep the raw value readable even if key rotated unexpectedly.
            return raw
