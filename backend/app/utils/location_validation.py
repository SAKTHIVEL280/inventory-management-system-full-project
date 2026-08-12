"""Country / state (region) validation for Customer and Supplier masters.

Rules enforced (frontend mirrors these; backend is the source of truth):
  * Country  -> must be a recognised country name. Continent names and any
    unrecognised token are rejected.
  * State    -> free-form region/state, but must NOT be a country name or a
    continent name (a common data-entry mistake).

Matching is case-insensitive and tolerant of a small set of common aliases
(USA, UK, UAE, ...). Blank values are allowed because these fields are optional.
"""
from __future__ import annotations

from app.utils.countries import COUNTRY_MASTER

# Case-insensitive lookup of the canonical country name.
_COUNTRY_LOOKUP: dict[str, str] = {name.lower(): name for name in COUNTRY_MASTER}

# Common shorthands users type -> canonical master name.
_COUNTRY_ALIASES: dict[str, str] = {
    "usa": "United States",
    "u.s.a.": "United States",
    "us": "United States",
    "u.s.": "United States",
    "united states of america": "United States",
    "america": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "great britain": "United Kingdom",
    "britain": "United Kingdom",
    "england": "United Kingdom",
    "uae": "United Arab Emirates",
    "u.a.e.": "United Arab Emirates",
    "south korea": "South Korea",
    "korea": "South Korea",
    "russia": "Russia",
    "czech republic": "Czechia",
}

# Continent / super-region names that must never be accepted as a country or state.
_CONTINENTS: set[str] = {
    "asia",
    "africa",
    "europe",
    "north america",
    "south america",
    "central america",
    "latin america",
    "antarctica",
    "oceania",
    "australia and oceania",
    "americas",
    "eurasia",
    "middle east",
    "sub-saharan africa",
    "caribbean",
    "scandinavia",
}


def _clean(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def canonical_country(value: str | None) -> str | None:
    """Return the canonical country name for ``value`` or ``None`` if unrecognised."""
    token = _clean(value).lower()
    if not token:
        return None
    if token in _COUNTRY_LOOKUP:
        return _COUNTRY_LOOKUP[token]
    if token in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[token]
    return None


def validate_country(value: str | None, *, field_label: str = "Country") -> str | None:
    """Validate + normalise a country name.

    Returns the canonical country name (blank -> ``None``). Raises ``ValueError``
    with a clear message for continents or any unrecognised value.
    """
    token = _clean(value)
    if not token:
        return None
    if token.lower() in _CONTINENTS:
        raise ValueError(
            f"{field_label} must be a valid country, not a continent (\"{token}\" is a continent)"
        )
    canonical = canonical_country(token)
    if canonical is None:
        raise ValueError(
            f"\"{token}\" is not a valid country name. Please enter a valid {field_label.lower()}."
        )
    return canonical


def validate_state(value: str | None, *, field_label: str = "State") -> str | None:
    """Validate a state/region.

    Regions vary too widely to enumerate, so any non-empty token is accepted
    EXCEPT a country name or a continent name (both are common mistakes).
    Returns the trimmed value (blank -> ``None``).
    """
    token = _clean(value)
    if not token:
        return None
    if token.lower() in _CONTINENTS:
        raise ValueError(
            f"{field_label} must be a state/region, not a continent (\"{token}\" is a continent)"
        )
    if canonical_country(token) is not None:
        raise ValueError(
            f"{field_label} must be a state/region, not a country (\"{token}\" is a country)"
        )
    return token
