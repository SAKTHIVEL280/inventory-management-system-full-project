"""Unit tests for the data-validation rules added across the ERP:
  * whole-number quantities (BE-262)
  * country / state location validation (BE-263)
  * Service Invoice mobile-number validation (BE-265)
All pure functions / regex — no database access."""
import pytest

from app.utils.quantity_validation import validate_whole_quantity
from app.utils.location_validation import validate_country, validate_state
from app.routers.service_invoice import _CONTACT_RE


# ── Whole-number quantities (BE-262) ─────────────────────────────────────────
def test_whole_quantity_accepts_integers():
    assert validate_whole_quantity(5, "Quantity") == 5
    assert validate_whole_quantity(5.0, "Quantity") == 5.0
    assert validate_whole_quantity(None, "Quantity") is None  # optional passes through


def test_whole_quantity_rejects_decimals():
    with pytest.raises(ValueError):
        validate_whole_quantity(5.5, "Quantity")
    with pytest.raises(ValueError):
        validate_whole_quantity(0.1, "Free quantity")


# ── Country / state validation (BE-263) ──────────────────────────────────────
def test_country_accepts_valid_and_aliases():
    assert validate_country("India") == "India"
    assert validate_country("usa") == "United States"       # alias -> canonical
    assert validate_country("  united kingdom ") == "United Kingdom"
    assert validate_country("") is None                     # optional


def test_country_rejects_continents_and_unknowns():
    with pytest.raises(ValueError):
        validate_country("Asia")            # continent
    with pytest.raises(ValueError):
        validate_country("Notaland")        # unknown token


def test_state_rejects_country_and_continent_names():
    assert validate_state("Karnataka") == "Karnataka"       # valid region
    with pytest.raises(ValueError):
        validate_state("India")             # a country is not a state
    with pytest.raises(ValueError):
        validate_state("Europe")            # a continent is not a state


# ── Service Invoice mobile validation (BE-265) ───────────────────────────────
def test_contact_regex_accepts_valid_indian_mobiles():
    for good in ("9876543210", "6000000000", "7500000000", "8123456789"):
        assert _CONTACT_RE.match(good), good


def test_contact_regex_rejects_invalid_prefixes_and_lengths():
    for bad in ("1234567890", "0987654321", "5555555555", "98765", "98765432101"):
        assert not _CONTACT_RE.match(bad), bad
