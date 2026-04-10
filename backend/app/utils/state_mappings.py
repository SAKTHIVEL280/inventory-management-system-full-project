"""State code helpers used by master-data validation flows."""
from __future__ import annotations

from typing import Optional


_STATE_CODE_ENTRIES: list[tuple[str, str, str]] = [
    ("01", "JK", "Jammu and Kashmir"),
    ("02", "HP", "Himachal Pradesh"),
    ("03", "PB", "Punjab"),
    ("04", "CH", "Chandigarh"),
    ("05", "UK", "Uttarakhand"),
    ("06", "HR", "Haryana"),
    ("07", "DL", "Delhi"),
    ("08", "RJ", "Rajasthan"),
    ("09", "UP", "Uttar Pradesh"),
    ("10", "BR", "Bihar"),
    ("11", "SK", "Sikkim"),
    ("12", "AR", "Arunachal Pradesh"),
    ("13", "NL", "Nagaland"),
    ("14", "MN", "Manipur"),
    ("15", "MZ", "Mizoram"),
    ("16", "TR", "Tripura"),
    ("17", "ML", "Meghalaya"),
    ("18", "AS", "Assam"),
    ("19", "WB", "West Bengal"),
    ("20", "JH", "Jharkhand"),
    ("21", "OR", "Odisha"),
    ("22", "CT", "Chhattisgarh"),
    ("23", "MP", "Madhya Pradesh"),
    ("24", "GJ", "Gujarat"),
    ("26", "DD", "Dadra and Nagar Haveli and Daman and Diu"),
    ("27", "MH", "Maharashtra"),
    ("28", "AP", "Andhra Pradesh"),
    ("29", "KA", "Karnataka"),
    ("30", "GA", "Goa"),
    ("31", "LD", "Lakshadweep"),
    ("32", "KL", "Kerala"),
    ("33", "TN", "Tamil Nadu"),
    ("34", "PY", "Puducherry"),
    ("35", "AN", "Andaman and Nicobar Islands"),
    ("36", "TS", "Telangana"),
    ("37", "LA", "Ladakh"),
    ("38", "LA", "Ladakh"),
]

_STATE_CODE_MAP: dict[str, str] = {}
_STATE_NAME_BY_CODE: dict[str, str] = {}
_STATE_ABBR_BY_CODE: dict[str, str] = {}
for _numeric, _abbr, _name in _STATE_CODE_ENTRIES:
    _STATE_CODE_MAP[_numeric] = _numeric
    _STATE_CODE_MAP[_abbr.upper()] = _numeric
    _STATE_CODE_MAP[_name.upper()] = _numeric
    _STATE_NAME_BY_CODE[_numeric] = _name
    _STATE_ABBR_BY_CODE[_numeric] = _abbr


def _normalize_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    token = " ".join(value.strip().upper().split())
    return token or None


def canonical_state_code(value: Optional[str]) -> Optional[str]:
    token = _normalize_text(value)
    if not token:
        return None
    if token.isdigit():
        token = token.zfill(2)
    return _STATE_CODE_MAP.get(token)


def state_name_from_code(value: Optional[str]) -> Optional[str]:
    code = canonical_state_code(value)
    if not code:
        return None
    return _STATE_NAME_BY_CODE.get(code)


def state_abbreviation_from_code(value: Optional[str]) -> Optional[str]:
    code = canonical_state_code(value)
    if not code:
        return None
    return _STATE_ABBR_BY_CODE.get(code)


def validate_and_autofill_state_fields(
    state_value: Optional[str],
    state_code_value: Optional[str],
    *,
    field_label: str = "State",
) -> tuple[Optional[str], Optional[str]]:
    state = (state_value or "").strip() or None
    code = (state_code_value or "").strip().upper() or None

    code_from_state = canonical_state_code(state)
    code_from_code = canonical_state_code(code)

    if code_from_code and not state:
        state = state_name_from_code(code_from_code)

    if state and code_from_code and code_from_state and code_from_state != code_from_code:
        raise ValueError(f"{field_label} does not match the given state code")

    if code_from_code:
        code = code_from_code
    elif code_from_state:
        code = code_from_state

    return state, code
