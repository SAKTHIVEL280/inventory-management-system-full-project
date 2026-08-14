"""Unit tests for per-invoice foreign-currency exchange-rate handling
(SAL-CUR-01). Pure functions / schema validation — no database access."""
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routers.sales import _resolve_invoice_currency, _round_invoice_total, BASE_CURRENCY
from app.schemas.sales import SalesInvoiceResponse, SalesInvoiceCreateRequest

_UUID = "2b1c9c5e-0000-4000-8000-000000000000"


def _payload(rate):
    return SimpleNamespace(exchange_rate=rate)


# ── Currency resolution (authoritative from the customer) ────────────────────
def test_base_currency_customer_forces_rate_one():
    for ccy in ("INR", "inr", "", None):
        code, rate = _resolve_invoice_currency(SimpleNamespace(currency_code=ccy), _payload(None))
        assert code == BASE_CURRENCY and rate == 1.0


def test_foreign_currency_requires_positive_rate():
    cust = SimpleNamespace(currency_code="USD")
    code, rate = _resolve_invoice_currency(cust, _payload(83.5))
    assert code == "USD" and rate == 83.5


def test_foreign_currency_missing_rate_rejected():
    with pytest.raises(HTTPException):
        _resolve_invoice_currency(SimpleNamespace(currency_code="USD"), _payload(None))


def test_foreign_currency_non_positive_rate_rejected():
    with pytest.raises(HTTPException):
        _resolve_invoice_currency(SimpleNamespace(currency_code="EUR"), _payload(0))
    with pytest.raises(HTTPException):
        _resolve_invoice_currency(SimpleNamespace(currency_code="EUR"), _payload(-5))


# ── Schema-level exchange_rate validation (> 0 when provided) ─────────────────
def test_create_request_rejects_non_positive_rate():
    line = {"product_id": _UUID, "quantity": 1, "unit_price": 100, "gst_rate": 0}
    with pytest.raises(ValidationError):
        SalesInvoiceCreateRequest(customer_id=_UUID, invoice_date=date.today(), exchange_rate=0, items=[line])


# ── Response base-currency (INR) total = total * exchange_rate ────────────────
def _resp(total, ccy="INR", rate=1.0):
    return SalesInvoiceResponse(
        id=_UUID, invoice_number="INV-1", customer_id=_UUID, invoice_date=date.today(),
        due_date=None, invoice_type="within_state", status="issued",
        total_amount=total, amount_paid=0, amount_due=total,
        currency_code=ccy, exchange_rate=rate, created_at=None,
    )


def test_base_currency_total_for_inr_is_identity():
    r = _resp(100000)
    assert r.base_currency == "INR" and r.base_currency_total == 100000


def test_base_currency_total_for_foreign_uses_rate():
    r = _resp(100000, "USD", 83.5)   # $1000.00 -> INR 83,500.00
    assert r.base_currency_total == 8350000


# ── Grand-total rounding: nearest ₹5 (down) for INR only; exact for foreign ───
def test_inr_total_rounds_down_to_nearest_five_rupees():
    assert _round_invoice_total(1503, "INR") == 1500   # ₹15.03 -> ₹15.00
    assert _round_invoice_total(150000, "INR") == 150000


def test_foreign_total_is_not_inr_rounded():
    # $18.00 must stay $18.00 — NOT truncated to $15.00 by the ₹5 rule.
    assert _round_invoice_total(1800, "USD") == 1800
    assert _round_invoice_total(599, "EUR") == 599
