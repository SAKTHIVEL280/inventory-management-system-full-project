"""Shared input validation helpers for query parameters."""
from __future__ import annotations

import re
from typing import Iterable

from fastapi import HTTPException


_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_TOKEN_RE = re.compile(r"^[a-z0-9_-]+$")


def normalize_search_query(value: str | None, *, max_length: int = 120) -> str | None:
    """Normalize user-provided search input and reject obviously malformed values."""
    if value is None:
        return None

    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > max_length:
        raise HTTPException(status_code=422, detail=f"search must be at most {max_length} characters")
    if _CONTROL_CHARS_RE.search(trimmed):
        raise HTTPException(status_code=422, detail="search contains invalid control characters")
    return trimmed


def validate_optional_token(value: str | None, *, field_name: str, allowed: Iterable[str]) -> str | None:
    """Validate optional lowercase token filters like status and party_type."""
    if value is None:
        return None
    token = value.strip().lower()
    if not token:
        return None
    if not _TOKEN_RE.match(token):
        raise HTTPException(status_code=422, detail=f"{field_name} contains invalid characters")
    allowed_set = {entry.strip().lower() for entry in allowed if entry}
    if token not in allowed_set:
        raise HTTPException(status_code=422, detail=f"Invalid {field_name}: {token}")
    return token
