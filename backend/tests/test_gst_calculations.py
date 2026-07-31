"""Unit tests for the GST calculation engine (pure functions, no database)."""
from app.services.gst_service import split_tax, calc_line_item


def test_split_tax_intra_state_cgst_sgst():
    # ₹100 taxable at 18% intra-state -> CGST 9% + SGST 9%.
    cgst, sgst, igst = split_tax(10000, 18, is_igst=False)
    assert (cgst, sgst, igst) == (900, 900, 0)


def test_split_tax_inter_state_igst():
    # ₹100 taxable at 18% inter-state -> IGST 18%.
    cgst, sgst, igst = split_tax(10000, 18, is_igst=True)
    assert (cgst, sgst, igst) == (0, 0, 1800)


def test_split_tax_not_applicable_is_zero():
    assert split_tax(10000, 18, gst_applicable=False) == (0, 0, 0)
    assert split_tax(0, 18) == (0, 0, 0)
    assert split_tax(10000, 0) == (0, 0, 0)


def test_calc_line_item_with_discount_intra_state():
    # qty 2 x ₹100, 10% discount, 18% GST intra-state.
    result = calc_line_item(quantity=2, unit_price=10000, discount_percent=10, gst_rate=18)
    assert result["gross"] == 20000
    assert result["discount"] == 2000
    assert result["taxable"] == 18000
    assert result["cgst"] == 1620
    assert result["sgst"] == 1620
    assert result["igst"] == 0
    assert result["total"] == 21240  # 18000 + 1620 + 1620


def test_calc_line_item_no_gst_when_not_applicable():
    result = calc_line_item(quantity=1, unit_price=5000, discount_percent=0, gst_rate=18, gst_applicable=False)
    assert result["cgst"] == 0 and result["sgst"] == 0 and result["igst"] == 0
    assert result["total"] == 5000
