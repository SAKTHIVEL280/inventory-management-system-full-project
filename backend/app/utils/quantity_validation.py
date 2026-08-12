"""Shared quantity validation.

Physical stock is counted in whole units across the ERP (Product, Purchase Order,
GRN, Sales and their returns). Fractional quantities are rejected at the schema
layer so the same rule is enforced for every write path (create, edit, return).

The validator only *rejects* fractional input; a whole value (e.g. ``5`` or
``5.0``) passes through unchanged, so existing stock/GST/amount calculations are
unaffected.
"""
from __future__ import annotations


def validate_whole_quantity(value, field_label: str = "Quantity"):
    """Return ``value`` unchanged if it is a whole number, else raise ValueError.

    ``None`` is passed through so optional fields keep their optionality; range
    checks (negative/zero) are intentionally left to existing per-schema rules so
    behaviour beyond the decimal check is not altered.
    """
    if value is None:
        return value
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_label} must be a whole number (decimals are not allowed)")
    if numeric != int(numeric):
        raise ValueError(f"{field_label} must be a whole number (decimals are not allowed)")
    return value
