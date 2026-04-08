"""GST calculation service.

Implements country-aware GST mode resolution:
- India only: GST applies (CGST+SGST for intra-state, IGST for inter-state)
- Non-India: GST does not apply
"""
from typing import TypedDict
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

_INDIA_COUNTRY_TOKENS = {
    "IN",
    "INDIA",
    "BHARAT",
    "REPUBLIC OF INDIA",
}


class TaxMode(TypedDict):
    gst_applicable: bool
    is_igst: bool
    use_utgst: bool


INVOICE_TYPE_WITHIN_STATE = "within_state"
INVOICE_TYPE_OTHER_STATES = "other_states"
INVOICE_TYPE_UNION_TERRITORY = "union_territory"
INVOICE_TYPE_EXPORT = "export_invoice"

ALLOWED_INVOICE_TYPES = {
    INVOICE_TYPE_EXPORT,
    INVOICE_TYPE_WITHIN_STATE,
    INVOICE_TYPE_OTHER_STATES,
    INVOICE_TYPE_UNION_TERRITORY,
}

_UNION_TERRITORY_CODES = {
    "01",  # Jammu and Kashmir
    "04",  # Chandigarh
    "07",  # Delhi
    "26",  # Dadra and Nagar Haveli and Daman and Diu
    "31",  # Lakshadweep
    "34",  # Puducherry
    "35",  # Andaman and Nicobar Islands
    "37",  # Ladakh
    "38",  # Ladakh (alternate newer code seen in some datasets)
}


def _normalize_state_code(raw: str | None) -> str | None:
    """Normalize any state format (numeric / abbreviation / full name) to numeric GST code."""
    if not raw:
        return None
    return _STATE_CODE_MAP.get(raw.strip().upper(), raw.strip().upper())


def _normalize_text(raw: str | None) -> str | None:
    if not raw:
        return None
    normalized = " ".join(raw.strip().upper().split())
    return normalized or None


def _is_india_country(country: str | None) -> bool:
    normalized = _normalize_text(country)
    return normalized in _INDIA_COUNTRY_TOKENS


def is_india_country(country: str | None) -> bool:
    """Public helper for India country validation across modules."""
    return _is_india_country(country)


def _state_token(state_code: str | None, state_name: str | None) -> str | None:
    code = _normalize_state_code(state_code)
    if code:
        return code
    name = _normalize_text(state_name)
    if not name:
        return None
    return _STATE_CODE_MAP.get(name, name)


def determine_tax_mode(db: Session, party_type: str, party_id: UUID) -> TaxMode:
    """Determine GST applicability and IGST mode for a customer/supplier transaction."""
    company = db.query(Company).first()
    if not company:
        return {"gst_applicable": False, "is_igst": False, "use_utgst": False}

    party_country: str | None = None
    party_state_code: str | None = None
    party_state_name: str | None = None
    supplier_business_type: str | None = None

    if party_type == "customer":
        party = db.query(Customer).filter(Customer.id == party_id, Customer.is_deleted == False).first()
        if not party:
            return {"gst_applicable": False, "is_igst": False, "use_utgst": False}
        party_country = party.billing_country
        party_state_code = party.billing_state_code
        party_state_name = party.billing_state
    elif party_type == "supplier":
        party = db.query(Supplier).filter(Supplier.id == party_id, Supplier.is_deleted == False).first()
        if not party:
            return {"gst_applicable": False, "is_igst": False, "use_utgst": False}
        party_country = party.billing_country
        party_state_code = party.state_code
        party_state_name = party.state
        supplier_business_type = party.business_type
    else:
        return {"gst_applicable": False, "is_igst": False, "use_utgst": False}

    # Backward compatibility:
    # If supplier country is blank but supplier is domestic, treat as India.
    normalized_country = _normalize_text(party_country)
    if party_type == "supplier" and not normalized_country:
        if (supplier_business_type or "").strip().lower() == "domestic":
            normalized_country = "INDIA"

    # Validation rule: country check comes first; apply Indian GST only for India.
    if normalized_country not in _INDIA_COUNTRY_TOKENS:
        return {"gst_applicable": False, "is_igst": False, "use_utgst": False}

    company_token = _state_token(company.state_code, company.state)
    party_token = _state_token(party_state_code, party_state_name)

    # If both locations are known, use them to decide intra/inter-state.
    if company_token and party_token:
        return {"gst_applicable": True, "is_igst": company_token != party_token, "use_utgst": False}

    # Fallback for India when state/state-code is incomplete: default to IGST.
    return {"gst_applicable": True, "is_igst": True, "use_utgst": False}


def invoice_type_tax_mode(invoice_type: str | None, fallback_is_igst: bool = False) -> TaxMode:
    """Map invoice type to tax application mode.

    Rules:
    - export_invoice: no GST
    - other_states: IGST
    - union_territory: CGST + UTGST
    - within_state: CGST + SGST
    """
    token = (invoice_type or "").strip().lower()
    if token == INVOICE_TYPE_EXPORT:
        return {"gst_applicable": False, "is_igst": False, "use_utgst": False}
    if token == INVOICE_TYPE_OTHER_STATES:
        return {"gst_applicable": True, "is_igst": True, "use_utgst": False}
    if token == INVOICE_TYPE_UNION_TERRITORY:
        return {"gst_applicable": True, "is_igst": False, "use_utgst": True}
    if token == INVOICE_TYPE_WITHIN_STATE:
        return {"gst_applicable": True, "is_igst": False, "use_utgst": False}
    return {"gst_applicable": True, "is_igst": fallback_is_igst, "use_utgst": False}


def determine_is_igst(db: Session, party_type: str, party_id: UUID) -> bool:
    """Backward-compatible helper that returns only the IGST flag."""
    return determine_tax_mode(db, party_type, party_id)["is_igst"]


def determine_default_invoice_type(db: Session, customer_id: UUID) -> str:
    """Derive default invoice type based on customer country/state and company location."""
    company = db.query(Company).first()
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.is_deleted == False).first()
    if not customer:
        return INVOICE_TYPE_WITHIN_STATE

    if not _is_india_country(customer.billing_country):
        return INVOICE_TYPE_EXPORT

    customer_token = _state_token(customer.billing_state_code, customer.billing_state)
    if customer_token in _UNION_TERRITORY_CODES:
        return INVOICE_TYPE_UNION_TERRITORY

    if not company:
        return INVOICE_TYPE_OTHER_STATES

    company_token = _state_token(company.state_code, company.state)
    if company_token and customer_token:
        if company_token == customer_token:
            return INVOICE_TYPE_WITHIN_STATE
        return INVOICE_TYPE_OTHER_STATES

    company_state = _normalize_text(company.state)
    customer_state = _normalize_text(customer.billing_state)
    if company_state and customer_state and company_state == customer_state:
        return INVOICE_TYPE_WITHIN_STATE

    return INVOICE_TYPE_OTHER_STATES


def split_tax(
    taxable_amount: int,
    gst_rate: int,
    is_igst: bool = False,
    gst_applicable: bool = True,
) -> tuple[int, int, int]:
    """
    Split GST into CGST+SGST or IGST based on mode.

    Args:
        taxable_amount: Amount to calculate tax on (in paise)
        gst_rate: GST rate as integer percentage (e.g. 18 for 18%)
        is_igst: If True, apply IGST only
        gst_applicable: If False, return zero tax for non-India transactions

    Returns:
        Tuple of (cgst_amount, sgst_amount, igst_amount)
    """
    if not gst_applicable or taxable_amount <= 0 or gst_rate <= 0:
        return 0, 0, 0

    if is_igst:
        igst = round(taxable_amount * gst_rate / 100)
        return 0, 0, igst

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
    gst_applicable: bool = True,
) -> dict:
    """
    Calculate all financial fields for a single line item.

    Args:
        quantity: Item quantity
        unit_price: Price per unit (in paise)
        discount_percent: Discount percentage
        gst_rate: GST rate (0, 5, 12, 18, 28)
        is_igst: If True, apply IGST; else split as CGST + SGST
        gst_applicable: If False, no GST is applied

    Returns:
        Dict with gross, discount, taxable, cgst, sgst, igst, total, gst_rate
    """
    gross = round(unit_price * quantity)
    discount = round(gross * discount_percent / 100)
    taxable = gross - discount
    effective_gst_rate = gst_rate if gst_applicable else 0
    cgst, sgst, igst = split_tax(taxable, effective_gst_rate, is_igst, gst_applicable)
    return {
        "gross": gross,
        "discount": discount,
        "taxable": taxable,
        "gst_rate": effective_gst_rate,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total": taxable + cgst + sgst + igst,
    }
