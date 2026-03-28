"""GST calculation service.

Fixes BUG-02: Implements IGST vs CGST/SGST auto-detection from state codes.
Centralizes all GST logic that was previously scattered across routers.
"""
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.customer import Customer
from app.models.supplier import Supplier


def determine_is_igst(db: Session, party_type: str, party_id: UUID) -> bool:
    """
    Determine whether IGST or CGST/SGST applies by comparing
    company state_code with party state_code.
    
    IGST applies when state codes differ (inter-state transaction).
    CGST/SGST applies when state codes match (intra-state transaction).
    
    Args:
        db: Database session
        party_type: 'customer' or 'supplier'
        party_id: UUID of the customer or supplier
    
    Returns:
        True if IGST, False if CGST/SGST
    """
    company = db.query(Company).first()
    if not company or not company.state_code:
        # If company state code not set, default to intra-state (CGST/SGST)
        return False

    if party_type == "customer":
        party = db.query(Customer).filter(
            Customer.id == party_id,
            Customer.is_deleted == False,
        ).first()
        party_state_code = party.billing_state_code if party else None
    elif party_type == "supplier":
        party = db.query(Supplier).filter(
            Supplier.id == party_id,
            Supplier.is_deleted == False,
        ).first()
        party_state_code = party.state_code if party else None
    else:
        return False

    if not party_state_code:
        # If party state code not set, default to intra-state
        return False

    # IGST when state codes are different (inter-state)
    return company.state_code != party_state_code


def split_tax(taxable_amount: int, gst_rate: int, is_igst: bool) -> tuple[int, int, int]:
    """
    Split GST into CGST, SGST, IGST components.
    
    Args:
        taxable_amount: Amount to calculate tax on (in paise)
        gst_rate: GST rate as integer percentage (e.g. 18 for 18%)
        is_igst: Whether to apply as IGST (True) or CGST+SGST (False)
    
    Returns:
        Tuple of (cgst_amount, sgst_amount, igst_amount)
    """
    if is_igst:
        igst = round(taxable_amount * gst_rate / 100)
        return 0, 0, igst
    else:
        half_rate = gst_rate / 2
        cgst = round(taxable_amount * half_rate / 100)
        sgst = round(taxable_amount * half_rate / 100)
        return cgst, sgst, 0


def calc_line_item(
    quantity: float,
    unit_price: int,
    discount_percent: float,
    gst_rate: int,
    is_igst: bool,
) -> dict:
    """
    Calculate all financial fields for a single line item.
    
    Args:
        quantity: Item quantity
        unit_price: Price per unit (in paise)
        discount_percent: Discount percentage
        gst_rate: GST rate (0, 5, 12, 18, 28)
        is_igst: Whether IGST applies
    
    Returns:
        Dict with gross, discount, taxable, cgst, sgst, igst, total
    """
    gross = round(unit_price * quantity)
    discount = round(gross * discount_percent / 100)
    taxable = gross - discount
    cgst, sgst, igst = split_tax(taxable, gst_rate, is_igst)
    return {
        "gross": gross,
        "discount": discount,
        "taxable": taxable,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total": taxable + cgst + sgst + igst,
    }
