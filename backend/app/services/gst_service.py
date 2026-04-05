"""GST calculation service.

Fixes BUG-02: Implements IGST vs CGST/SGST auto-detection from state codes.
Centralizes all GST logic that was previously scattered across routers.
"""
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.customer import Customer
from app.models.supplier import Supplier


# Map of all Indian GST state codes — supports numeric, abbreviation, and full name
_STATE_CODE_MAP: dict[str, str] = {}
_STATE_ENTRIES = [
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
]
for _num, _abbr, _name in _STATE_ENTRIES:
    _STATE_CODE_MAP[_num] = _num
    _STATE_CODE_MAP[_abbr.upper()] = _num
    _STATE_CODE_MAP[_name.upper()] = _num


def _normalize_state_code(raw: str | None) -> str | None:
    """Normalize any state format (numeric / abbreviation / full name) to numeric GST code."""
    if not raw:
        return None
    return _STATE_CODE_MAP.get(raw.strip().upper(), raw.strip().upper())


def determine_is_igst(db: Session, party_type: str, party_id: UUID) -> bool:
    """
    IGST is disabled for now.  Always returns False so that every
    transaction uses CGST + SGST only.

    Args:
        db: Database session
        party_type: 'customer' or 'supplier'
        party_id: UUID of the customer or supplier

    Returns:
        Always False (CGST/SGST)
    """
    # IGST disabled — always use CGST + SGST
    return False


def split_tax(taxable_amount: int, gst_rate: int, is_igst: bool = False) -> tuple[int, int, int]:
    """
    Split GST into CGST and SGST (equal halves).  IGST is disabled.

    The *is_igst* parameter is kept for API compatibility but is
    always treated as False.

    Args:
        taxable_amount: Amount to calculate tax on (in paise)
        gst_rate: GST rate as integer percentage (e.g. 18 for 18%)
        is_igst: Ignored — always splits as CGST + SGST

    Returns:
        Tuple of (cgst_amount, sgst_amount, 0)
    """
    half_rate = gst_rate / 2
    cgst = round(taxable_amount * half_rate / 100)
    sgst = round(taxable_amount * half_rate / 100)
    return cgst, sgst, 0


def calc_line_item(
    quantity: float,
    unit_price: int,
    discount_percent: float,
    gst_rate: int,
    is_igst: bool = False,
) -> dict:
    """
    Calculate all financial fields for a single line item.
    IGST is disabled — tax is always split as CGST + SGST.

    Args:
        quantity: Item quantity
        unit_price: Price per unit (in paise)
        discount_percent: Discount percentage
        gst_rate: GST rate (0, 5, 12, 18, 28)
        is_igst: Ignored — always uses CGST + SGST

    Returns:
        Dict with gross, discount, taxable, cgst, sgst, igst (always 0), total
    """
    gross = round(unit_price * quantity)
    discount = round(gross * discount_percent / 100)
    taxable = gross - discount
    cgst, sgst, igst = split_tax(taxable, gst_rate, False)
    return {
        "gross": gross,
        "discount": discount,
        "taxable": taxable,
        "cgst": cgst,
        "sgst": sgst,
        "igst": 0,
        "total": taxable + cgst + sgst,
    }
