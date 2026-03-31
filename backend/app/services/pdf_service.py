"""PDF generation service using WeasyPrint.

Generates GST-compliant Purchase Order and Tax Invoice PDFs with a
single-page-optimized A4 layout using Jinja-style HTML templates.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import io
from pathlib import Path
from typing import Any
from uuid import UUID

from jinja2 import Template
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.customer import Customer
from app.models.product import Product
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.sales import SalesInvoice, SalesInvoiceItem, SalesOrder
from app.models.supplier import Supplier


ROOT_DIR = Path(__file__).resolve().parents[2]


DOCUMENT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{{ doc_title }} - {{ doc_number }}</title>
  <style>
    @page {
      size: A4;
      margin: 1cm;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      color: #1f2937;
      font-family: "Inter", "Roboto", "Segoe UI", Arial, sans-serif;
      font-size: 10pt;
      line-height: 1.28;
    }

    .doc-shell {
      min-height: 100%;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      padding: 8px;
    }

    .company-block {
      flex: 1 1 58%;
      display: flex;
      gap: 10px;
      align-items: flex-start;
    }

    .logo {
      width: 64px;
      height: 64px;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      background: #f9fafb;
      font-size: 8pt;
      color: #6b7280;
      text-align: center;
      padding: 4px;
    }

    .logo img {
      width: 100%;
      height: 100%;
      object-fit: contain;
    }

    .company-meta h1 {
      margin: 0;
      font-size: 13pt;
      line-height: 1.2;
    }

    .company-meta .line {
      margin-top: 2px;
      font-size: 8.8pt;
      color: #4b5563;
      overflow-wrap: anywhere;
    }

    .doc-meta {
      flex: 1 1 42%;
      border-left: 1px solid #e5e7eb;
      padding-left: 10px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .doc-title {
      margin: 0;
      text-align: right;
      font-size: 16pt;
      letter-spacing: 0.4px;
      font-weight: 800;
      color: #111827;
    }

    .meta-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 8.8pt;
      table-layout: fixed;
    }

    .meta-table td {
      border: 1px solid #d1d5db;
      padding: 4px 5px;
      vertical-align: top;
      overflow-wrap: anywhere;
      word-break: break-word;
    }

    .meta-label {
      width: 34%;
      font-weight: 700;
      color: #374151;
      background: #f9fafb;
    }

    .meta-value {
      overflow-wrap: anywhere;
      word-break: break-all;
      white-space: normal;
      display: block;
    }

    .address-row {
      display: flex;
      gap: 10px;
    }

    .address-box {
      flex: 1;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      padding: 7px;
      min-height: 80px;
    }

    .address-box h3 {
      margin: 0 0 5px 0;
      font-size: 9pt;
      color: #111827;
      border-bottom: 1px solid #e5e7eb;
      padding-bottom: 3px;
    }

    .address-line {
      margin: 1px 0;
      font-size: 8.8pt;
      color: #374151;
      overflow-wrap: anywhere;
    }

    .table-wrap {
      border: 1px solid #d1d5db;
      border-radius: 6px;
      overflow: hidden;
    }

    table.items {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 8pt;
    }

    table.items col:nth-child(1) { width: 3.5%; }
    table.items col:nth-child(2) { width: 22%; }
    table.items col:nth-child(3) { width: 7%; }
    table.items col:nth-child(4) { width: 6%; }
    table.items col:nth-child(5) { width: 6%; }
    table.items col:nth-child(6) { width: 8%; }
    table.items col:nth-child(7) { width: 6.5%; }
    table.items col:nth-child(8) { width: 9%; }
    table.items col:nth-child(9) { width: 8%; }
    table.items col:nth-child(10) { width: 6%; }
    table.items col:nth-child(11) { width: 6%; }
    table.items col:nth-child(12) { width: 12%; }

    table.items th {
      background: #eef2ff;
      color: #111827;
      font-weight: 700;
      border: 1px solid #d1d5db;
      padding: 4px 2px;
      text-align: center;
      vertical-align: middle;
      line-height: 1.2;
    }

    table.items td {
      border: 1px solid #e5e7eb;
      padding: 3px 2px;
      vertical-align: top;
      line-height: 1.18;
      word-wrap: break-word;
      overflow-wrap: anywhere;
    }

    .money {
      font-variant-numeric: tabular-nums;
      letter-spacing: 0;
      white-space: nowrap;
      word-break: keep-all;
    }

    .right {
      text-align: right;
      white-space: nowrap;
    }
    .center { text-align: center; }

    .summary-row {
      display: table;
      width: 100%;
      table-layout: fixed;
    }

    .left-notes {
      display: table-cell;
      width: 56%;
      padding-right: 8px;
      display: flex;
      flex-direction: column;
      gap: 7px;
      min-width: 0;
      vertical-align: top;
    }

    .summary-wrap {
      display: table-cell;
      width: 44%;
      vertical-align: top;
    }

    .words,
    .notes {
      border: 1px solid #d1d5db;
      border-radius: 6px;
      padding: 6px 8px;
      font-size: 8.8pt;
      overflow-wrap: anywhere;
      word-break: break-word;
      white-space: normal;
    }

    .block-label {
      display: block;
      margin-bottom: 2px;
      font-weight: 700;
      color: #111827;
    }

    .break-any {
      overflow-wrap: anywhere;
      word-break: break-all;
      white-space: normal;
      display: block;
    }

    .gstin-text {
      overflow-wrap: anywhere;
      word-break: break-all;
      white-space: normal;
    }

    .words strong,
    .notes strong {
      display: inline-block;
      margin-right: 4px;
      color: #111827;
    }

    .summary {
      width: 100%;
      border-collapse: collapse;
      font-size: 9pt;
      table-layout: fixed;
    }

    .summary td {
      border: 1px solid #d1d5db;
      padding: 5px 7px;
      white-space: nowrap;
    }

    body.compact-table table.items {
      font-size: 7.4pt;
    }

    body.compact-table table.items th {
      padding: 3px 2px;
      line-height: 1.1;
    }

    body.compact-table table.items td {
      padding: 2px 2px;
      line-height: 1.1;
    }

    body.compact-table .address-box {
      min-height: 72px;
      padding: 6px;
    }

    body.compact-table .company-meta h1 {
      font-size: 12pt;
    }

    body.compact-table .doc-title {
      font-size: 14.5pt;
    }

    body.stack-summary .summary-row {
      display: block;
    }

    body.stack-summary .left-notes,
    body.stack-summary .summary-wrap {
      display: block;
      width: 100%;
      padding-right: 0;
      margin-bottom: 6px;
    }

    body.stack-summary .summary {
      width: 100%;
    }

    .summary td:first-child {
      background: #f9fafb;
      font-weight: 700;
      color: #374151;
    }

    .summary .grand td {
      font-size: 10pt;
      font-weight: 800;
      background: #111827;
      color: #fff;
      border-color: #111827;
    }

    .footer {
      margin-top: auto;
      display: flex;
      justify-content: flex-end;
      align-items: flex-end;
      min-height: 48px;
    }

    .signature {
      width: 220px;
      text-align: center;
      font-size: 9pt;
      color: #374151;
    }

    .signature .line {
      border-top: 1px solid #111827;
      margin-top: 24px;
      padding-top: 4px;
      font-weight: 700;
    }

    body.purchase-order .doc-title::before { content: "PURCHASE ORDER"; }
    body.tax-invoice .doc-title::before { content: "TAX INVOICE"; }
  </style>
</head>
<body class="{{ doc_class }} {{ layout_mode }}">
  <div class="doc-shell">
    <header class="header">
      <div class="company-block">
        <div class="logo">
          {% if company_logo %}
            <img src="{{ company_logo }}" alt="Logo" />
          {% else %}
            LOGO
          {% endif %}
        </div>
        <div class="company-meta">
          <h1>{{ company_name }}</h1>
          <div class="line">{{ company_address }}</div>
          <div class="line">GSTIN: <span class="gstin-text">{{ company_gstin }}</span></div>
          <div class="line">{{ company_contact }}</div>
        </div>
      </div>
      <div class="doc-meta">
        <h2 class="doc-title"></h2>
        <table class="meta-table">
          <tr>
            <td class="meta-label">{{ number_label }}</td>
            <td><span class="meta-value">{{ doc_number }}</span></td>
          </tr>
          <tr>
            <td class="meta-label">Date</td>
            <td><span class="meta-value">{{ doc_date }}</span></td>
          </tr>
          <tr>
            <td class="meta-label">GSTIN</td>
            <td><span class="meta-value gstin-text">{{ party_gstin }}</span></td>
          </tr>
        </table>
      </div>
    </header>

    <section class="address-row">
      <div class="address-box">
        <h3>Bill To</h3>
        <div class="address-line"><strong>{{ bill_to_name }}</strong></div>
        <div class="address-line">{{ bill_to_address }}</div>
        <div class="address-line">GSTIN: <span class="gstin-text">{{ bill_to_gstin }}</span></div>
      </div>
      <div class="address-box">
        <h3>Ship To</h3>
        <div class="address-line"><strong>{{ ship_to_name }}</strong></div>
        <div class="address-line">{{ ship_to_address }}</div>
        <div class="address-line">GSTIN: <span class="gstin-text">{{ ship_to_gstin }}</span></div>
      </div>
    </section>

    <section class="table-wrap">
      <table class="items">
        <colgroup>
          <col /><col /><col /><col /><col /><col /><col /><col /><col /><col /><col /><col />
        </colgroup>
        <thead>
          <tr>
            <th>#</th>
            <th>Item Description</th>
            <th>Batch</th>
            <th>MFG</th>
            <th>EXP</th>
            <th>HSN</th>
            <th>Qty</th>
            <th>Rate</th>
            <th>MRP</th>
            <th>CGST (%)</th>
            <th>SGST (%)</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody>
          {% for row in rows %}
          <tr>
            <td class="center">{{ row.sr }}</td>
            <td>{{ row.description }}</td>
            <td class="center">{{ row.batch }}</td>
            <td class="center">{{ row.mfg }}</td>
            <td class="center">{{ row.exp }}</td>
            <td class="center">{{ row.hsn }}</td>
            <td class="right">{{ row.qty }}</td>
            <td class="right money">{{ row.rate }}</td>
            <td class="right money">{{ row.mrp }}</td>
            <td class="right">{{ row.cgst_pct }}</td>
            <td class="right">{{ row.sgst_pct }}</td>
            <td class="right money">{{ row.amount }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </section>

    <section class="summary-row">
      <div class="left-notes">
        <div class="words"><span class="block-label">Total in Words:</span><span class="break-any">{{ total_in_words }}</span></div>
        <div class="notes"><span class="block-label">Notes:</span><span class="break-any">{{ notes }}</span></div>
      </div>
      <div class="summary-wrap">
        <table class="summary">
          <tr><td>Sub-Total</td><td class="right money">{{ subtotal }}</td></tr>
          <tr><td>CGST Total</td><td class="right money">{{ cgst_total }}</td></tr>
          <tr><td>SGST Total</td><td class="right money">{{ sgst_total }}</td></tr>
          {% if igst_total %}<tr><td>IGST Total</td><td class="right money">{{ igst_total }}</td></tr>{% endif %}
          <tr class="grand"><td>Grand Total</td><td class="right money">{{ grand_total }}</td></tr>
        </table>
      </div>
    </section>

    <footer class="footer">
      <div class="signature">
        <div class="line">Authorized Signature</div>
      </div>
    </footer>
  </div>
</body>
</html>
"""


def _format_date(value: date | datetime | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime("%d-%m-%Y")


def _format_currency(paise: int, currency_code: str = "INR") -> str:
    symbols = {"INR": "Rs.", "USD": "$", "EUR": "EUR", "GBP": "GBP"}
    amount = (paise or 0) / 100
    symbol = symbols.get(currency_code, currency_code)
    return f"{symbol}{amount:,.2f}"


def _decimal_to_str(value: Decimal | float | int | None) -> str:
    if value is None:
        return "0"
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def _safe_text(value: Any) -> str:
    return str(value).strip() if value is not None and str(value).strip() else "-"


def _amount_in_words(paise: int) -> str:
    ones = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen",
    ]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def words(n: int) -> str:
        if n == 0:
            return ""
        if n < 20:
            return ones[n]
        if n < 100:
            return tens[n // 10] + (" " + ones[n % 10] if n % 10 else "")
        if n < 1000:
            return ones[n // 100] + " Hundred" + (" and " + words(n % 100) if n % 100 else "")
        if n < 100000:
            return words(n // 1000) + " Thousand" + (" " + words(n % 1000) if n % 1000 else "")
        if n < 10000000:
            return words(n // 100000) + " Lakh" + (" " + words(n % 100000) if n % 100000 else "")
        return words(n // 10000000) + " Crore" + (" " + words(n % 10000000) if n % 10000000 else "")

    rupees = (paise or 0) // 100
    paisa = (paise or 0) % 100

    chunks = []
    if rupees:
        chunks.append(f"Indian Rupees {words(rupees)}")
    else:
        chunks.append("Indian Rupees Zero")
    if paisa:
        chunks.append(f"and {words(paisa)} Paise")
    return " ".join(chunks) + " Only"


def _resolve_logo_src(company: Company | None) -> str | None:
    if not company or not company.logo_url:
        return None

    logo_url = str(company.logo_url)
    if logo_url.startswith("/static/"):
        local_path = ROOT_DIR / logo_url.lstrip("/")
        if local_path.exists():
            return local_path.resolve().as_uri()
        return None

    possible = Path(logo_url)
    if possible.exists():
        return possible.resolve().as_uri()
    return None


def _render_pdf(context: dict[str, Any]) -> bytes:
    html = Template(DOCUMENT_TEMPLATE).render(**context)
    try:
        # Primary renderer (requested): WeasyPrint.
        # On Windows it requires GTK/Pango runtime libraries.
        from weasyprint import HTML

        return HTML(string=html, base_url=str(ROOT_DIR)).write_pdf()
    except Exception:
        # Safe fallback so PDF features don't break if native libs are missing.
        from xhtml2pdf import pisa

        buffer = io.BytesIO()
        status = pisa.CreatePDF(src=html, dest=buffer, encoding="utf-8")
        if status.err:
            raise RuntimeError(
                "PDF generation failed: WeasyPrint runtime libraries missing and fallback renderer failed."
            )
        buffer.seek(0)
        return buffer.read()


def _build_company_address(company: Company | None) -> str:
    if not company:
        return "-"
    parts = [company.address_line1, company.address_line2, company.city, company.state, company.pincode]
    return ", ".join([p.strip() for p in parts if p and p.strip()]) or "-"


def _layout_mode(rows: list[dict[str, str]], total_in_words: str, notes: str) -> str:
  row_count = len(rows)
  max_desc = max((len(r.get("description", "")) for r in rows), default=0)
  max_money_len = max((max(len(r.get("rate", "")), len(r.get("mrp", "")), len(r.get("amount", ""))) for r in rows), default=0)

  classes: list[str] = []
  if row_count >= 8 or max_desc >= 40 or max_money_len >= 11:
    classes.append("compact-table")
  if len(total_in_words or "") >= 70 or len(notes or "") >= 80:
    classes.append("stack-summary")
  return " ".join(classes)


def generate_po_pdf(db: Session, po_id: UUID) -> bytes:
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise ValueError("Purchase Order not found")

    company = db.query(Company).first()
    supplier = db.query(Supplier).filter(Supplier.id == po.supplier_id).first()
    items = (
        db.query(PurchaseOrderItem)
        .filter(PurchaseOrderItem.purchase_order_id == po.id, PurchaseOrderItem.is_deleted == False)
        .all()
    )

    rows: list[dict[str, str]] = []
    currency = po.currency_code or "INR"
    for idx, item in enumerate(items, start=1):
        product = db.query(Product).filter(Product.id == item.product_id).first()
        gst_rate = int(item.gst_rate or 0)
        cgst_pct = f"{gst_rate / 2:.1f}" if item.cgst_amount else "0"
        sgst_pct = f"{gst_rate / 2:.1f}" if item.sgst_amount else "0"
        rows.append(
            {
                "sr": str(idx),
                "description": _safe_text((item.description or (product.name if product else ""))),
                "batch": "-",
                "mfg": "-",
                "exp": "-",
                "hsn": _safe_text(product.hsn_code if product else None),
                "qty": _decimal_to_str(item.quantity),
                "rate": _format_currency(int(item.unit_price or 0), currency),
                "mrp": _format_currency(int(item.unit_price or 0), currency),
                "cgst_pct": cgst_pct,
                "sgst_pct": sgst_pct,
                "amount": _format_currency(int(item.total_amount or 0), currency),
            }
        )

    if not rows:
        rows.append(
            {
                "sr": "1",
                "description": "-",
                "batch": "-",
                "mfg": "-",
                "exp": "-",
                "hsn": "-",
                "qty": "0",
                "rate": _format_currency(0, currency),
                "mrp": _format_currency(0, currency),
                "cgst_pct": "0",
                "sgst_pct": "0",
                "amount": _format_currency(0, currency),
            }
        )

    notes_text = _safe_text(po.notes)
    total_words = _amount_in_words(int(po.total_amount or 0))

    context = {
        "doc_class": "purchase-order",
      "layout_mode": _layout_mode(rows, total_words, notes_text),
        "doc_title": "Purchase Order",
        "number_label": "PO Number",
        "doc_number": _safe_text(po.po_number),
        "doc_date": _format_date(po.order_date),
        "company_logo": _resolve_logo_src(company),
        "company_name": _safe_text(company.name if company else None),
        "company_address": _build_company_address(company),
        "company_gstin": _safe_text(company.gstin if company else None),
        "company_contact": _safe_text(company.phone if company and company.phone else (company.email if company else None)),
        "party_gstin": _safe_text(supplier.gstin if supplier else None),
        "bill_to_name": _safe_text(supplier.company_name if supplier else None),
        "bill_to_address": _safe_text(
            ", ".join(
                [p.strip() for p in [supplier.address_line1 if supplier else None, supplier.address_line2 if supplier else None, supplier.city if supplier else None, supplier.state if supplier else None, supplier.pincode if supplier else None] if p and p.strip()]
            )
        ),
        "bill_to_gstin": _safe_text(supplier.gstin if supplier else None),
        "ship_to_name": _safe_text(company.name if company else None),
        "ship_to_address": _build_company_address(company),
        "ship_to_gstin": _safe_text(company.gstin if company else None),
        "rows": rows,
        "subtotal": _format_currency(int(po.subtotal or 0), currency),
        "cgst_total": _format_currency(int(po.total_cgst or 0), currency),
        "sgst_total": _format_currency(int(po.total_sgst or 0), currency),
        "igst_total": _format_currency(int(po.total_igst or 0), currency) if int(po.total_igst or 0) else "",
        "grand_total": _format_currency(int(po.total_amount or 0), currency),
        "total_in_words": total_words,
        "notes": notes_text,
    }
    return _render_pdf(context)


def generate_invoice_pdf(db: Session, invoice_id: UUID) -> bytes:
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id).first()
    if not invoice:
        raise ValueError("Invoice not found")

    company = db.query(Company).first()
    customer = db.query(Customer).filter(Customer.id == invoice.customer_id).first()
    sales_order = db.query(SalesOrder).filter(SalesOrder.id == invoice.sales_order_id).first() if invoice.sales_order_id else None
    items = (
        db.query(SalesInvoiceItem)
        .filter(SalesInvoiceItem.invoice_id == invoice.id, SalesInvoiceItem.is_deleted == False)
        .all()
    )

    rows: list[dict[str, str]] = []
    for idx, item in enumerate(items, start=1):
        product = db.query(Product).filter(Product.id == item.product_id).first()
        gst_rate = int(item.gst_rate or 0)
        cgst_pct = f"{gst_rate / 2:.1f}" if item.cgst_amount else "0"
        sgst_pct = f"{gst_rate / 2:.1f}" if item.sgst_amount else "0"
        rows.append(
            {
                "sr": str(idx),
                "description": _safe_text((item.description or (product.name if product else ""))),
                "batch": "-",
                "mfg": "-",
                "exp": "-",
                "hsn": _safe_text(product.hsn_code if product else None),
                "qty": _decimal_to_str(item.quantity),
                "rate": _format_currency(int(item.unit_price or 0), "INR"),
                "mrp": _format_currency(int(item.mrp or item.unit_price or 0), "INR"),
                "cgst_pct": cgst_pct,
                "sgst_pct": sgst_pct,
                "amount": _format_currency(int(item.total_amount or 0), "INR"),
            }
        )

    if not rows:
        rows.append(
            {
                "sr": "1",
                "description": "-",
                "batch": "-",
                "mfg": "-",
                "exp": "-",
                "hsn": "-",
                "qty": "0",
                "rate": _format_currency(0, "INR"),
                "mrp": _format_currency(0, "INR"),
                "cgst_pct": "0",
                "sgst_pct": "0",
                "amount": _format_currency(0, "INR"),
            }
        )

    billing_parts = [
        customer.billing_address_line1 if customer else None,
        customer.billing_address_line2 if customer else None,
        customer.billing_city if customer else None,
        customer.billing_state if customer else None,
        customer.billing_pincode if customer else None,
    ]
    shipping_parts = [
        customer.shipping_address_line1 if customer else None,
        customer.shipping_address_line2 if customer else None,
        customer.shipping_city if customer else None,
        customer.shipping_state if customer else None,
        customer.shipping_pincode if customer else None,
    ]

    ship_to_address = ", ".join([p.strip() for p in shipping_parts if p and p.strip()])
    if not ship_to_address:
        ship_to_address = ", ".join([p.strip() for p in billing_parts if p and p.strip()])

    notes_text = _safe_text(invoice.notes if invoice.notes else (f"Sales Order: {sales_order.so_number}" if sales_order else "-"))
    total_words = _amount_in_words(int(invoice.total_amount or 0))

    context = {
        "doc_class": "tax-invoice",
      "layout_mode": _layout_mode(rows, total_words, notes_text),
        "doc_title": "Tax Invoice",
        "number_label": "Invoice Number",
        "doc_number": _safe_text(invoice.invoice_number),
        "doc_date": _format_date(invoice.invoice_date),
        "company_logo": _resolve_logo_src(company),
        "company_name": _safe_text(company.name if company else None),
        "company_address": _build_company_address(company),
        "company_gstin": _safe_text(company.gstin if company else None),
        "company_contact": _safe_text(company.phone if company and company.phone else (company.email if company else None)),
        "party_gstin": _safe_text(customer.gstin if customer else None),
        "bill_to_name": _safe_text(customer.company_name if customer else None),
        "bill_to_address": _safe_text(", ".join([p.strip() for p in billing_parts if p and p.strip()])),
        "bill_to_gstin": _safe_text(customer.gstin if customer else None),
        "ship_to_name": _safe_text(customer.company_name if customer else None),
        "ship_to_address": _safe_text(ship_to_address),
        "ship_to_gstin": _safe_text(customer.gstin if customer else None),
        "rows": rows,
        "subtotal": _format_currency(int(invoice.subtotal or 0), "INR"),
        "cgst_total": _format_currency(int(invoice.total_cgst or 0), "INR"),
        "sgst_total": _format_currency(int(invoice.total_sgst or 0), "INR"),
        "igst_total": _format_currency(int(invoice.total_igst or 0), "INR") if int(invoice.total_igst or 0) else "",
        "grand_total": _format_currency(int(invoice.total_amount or 0), "INR"),
        "total_in_words": total_words,
        "notes": notes_text,
    }
    return _render_pdf(context)
