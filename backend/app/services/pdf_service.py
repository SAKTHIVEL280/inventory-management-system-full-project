"""PDF generation service for Purchase Orders and Invoices.

Uses xhtml2pdf (pure Python) to convert HTML templates to PDF.
Matches the professional format from the reference PO image.
"""
import io
import os
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.supplier import Supplier
from app.models.customer import Customer
from app.models.product import Product
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.sales import SalesInvoice, SalesInvoiceItem, SalesOrder


def _amount_in_words(paise: int) -> str:
    """Convert amount in paise to Indian English words."""
    ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
            'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
            'Seventeen', 'Eighteen', 'Nineteen']
    tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']

    def _num_to_words(n: int) -> str:
        if n == 0:
            return ''
        if n < 20:
            return ones[n]
        if n < 100:
            return tens[n // 10] + ((' ' + ones[n % 10]) if n % 10 else '')
        if n < 1000:
            return ones[n // 100] + ' Hundred' + ((' and ' + _num_to_words(n % 100)) if n % 100 else '')
        if n < 100000:
            return _num_to_words(n // 1000) + ' Thousand' + ((' ' + _num_to_words(n % 1000)) if n % 1000 else '')
        if n < 10000000:
            return _num_to_words(n // 100000) + ' Lakh' + ((' ' + _num_to_words(n % 100000)) if n % 100000 else '')
        return _num_to_words(n // 10000000) + ' Crore' + ((' ' + _num_to_words(n % 10000000)) if n % 10000000 else '')

    rupees = paise // 100
    paisa = paise % 100

    result = ''
    if rupees > 0:
        result = 'Indian Rupees ' + _num_to_words(rupees)
    if paisa > 0:
        if result:
            result += ' and '
        result += _num_to_words(paisa) + ' Paise'
    if not result:
        result = 'Indian Rupees Zero'
    return result + ' Only'


def _format_currency(paise: int, currency_code: str = 'INR') -> str:
    """Format paise to currency display."""
    symbols = {'INR': '₹', 'USD': '$', 'EUR': '€', 'GBP': '£'}
    symbol = symbols.get(currency_code, currency_code + ' ')
    amount = paise / 100
    return f"{symbol}{amount:,.2f}"


def _get_common_styles() -> str:
    """Shared CSS for all PDFs."""
    return """
    <style>
        @page { size: A4; margin: 1.5cm; }
        body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; color: #333; margin: 0; padding: 0; }
        .header-table { width: 100%; border: none; margin-bottom: 10px; }
        .header-table td { border: none; padding: 5px; vertical-align: top; }
        .company-name { font-size: 16pt; font-weight: bold; color: #1a1a2e; margin: 0; }
        .company-detail { font-size: 8pt; color: #666; margin: 0; }
        .doc-title { font-size: 20pt; font-weight: bold; text-align: right; color: #1a1a2e; }
        .info-table { width: 100%; border-collapse: collapse; margin-bottom: 10px; border: 1px solid #ccc; }
        .info-table td { padding: 4px 8px; font-size: 9pt; border: 1px solid #ccc; }
        .info-label { font-weight: bold; color: #555; width: 120px; background: #f8f9fa; }
        .items-table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        .items-table th { background: #1a1a2e; color: white; padding: 6px 8px; font-size: 8pt; text-align: center; font-weight: bold; }
        .items-table td { padding: 5px 8px; font-size: 9pt; border: 1px solid #ddd; }
        .items-table tr:nth-child(even) { background: #f9f9f9; }
        .text-right { text-align: right; }
        .text-center { text-align: center; }
        .text-left { text-align: left; }
        .totals-table { width: 50%; margin-left: auto; border-collapse: collapse; }
        .totals-table td { padding: 4px 8px; font-size: 9pt; border: 1px solid #ddd; }
        .totals-table .total-label { text-align: right; font-weight: bold; background: #f8f9fa; }
        .totals-table .grand-total { background: #1a1a2e; color: white; font-size: 10pt; font-weight: bold; }
        .amount-words { border: 1px solid #ccc; padding: 8px; font-size: 9pt; margin: 10px 0; background: #f8f9fa; }
        .amount-words strong { color: #1a1a2e; }
        .notes-section { margin-top: 15px; font-size: 8pt; }
        .notes-section strong { display: block; margin-bottom: 3px; }
        .signature-area { margin-top: 30px; text-align: right; }
        .signature-line { border-top: 1px solid #333; width: 200px; margin-left: auto; padding-top: 5px; text-align: center; font-size: 9pt; font-weight: bold; }
        .logo-img { max-width: 80px; max-height: 80px; }
    </style>
    """


def generate_po_pdf(db: Session, po_id: UUID) -> bytes:
    """Generate a professional Purchase Order PDF."""
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise ValueError("Purchase Order not found")

    supplier = db.query(Supplier).filter(Supplier.id == po.supplier_id).first()
    company = db.query(Company).first()
    items = db.query(PurchaseOrderItem).filter(
        PurchaseOrderItem.purchase_order_id == po.id,
        PurchaseOrderItem.is_deleted == False,
    ).all()

    # Build item rows
    item_rows = ""
    for idx, item in enumerate(items, 1):
        product = db.query(Product).filter(Product.id == item.product_id).first()
        product_name = product.name if product else "Unknown"
        hsn = product.hsn_code if product else ""
        uom = "Pcs"  # Default

        cgst_pct = float(item.gst_rate) / 2 if item.cgst_amount > 0 else 0
        sgst_pct = float(item.gst_rate) / 2 if item.sgst_amount > 0 else 0
        igst_pct = float(item.gst_rate) if item.igst_amount > 0 else 0

        currency = getattr(po, 'currency_code', 'INR') or 'INR'

        item_rows += f"""
        <tr>
            <td class="text-center">{idx}</td>
            <td class="text-left">{product_name}</td>
            <td class="text-center">{hsn}</td>
            <td class="text-right">{float(item.quantity):.2f}</td>
            <td class="text-center">{uom}</td>
            <td class="text-right">{_format_currency(item.unit_price, currency)}</td>
            <td class="text-right">{float(item.discount_percent):.2f}</td>
            <td class="text-right">{cgst_pct:.1f}%</td>
            <td class="text-right">{sgst_pct:.1f}%</td>
            <td class="text-right">{_format_currency(item.total_amount, currency)}</td>
        </tr>
        """

    currency_code = getattr(po, 'currency_code', 'INR') or 'INR'
    exchange_rate = float(getattr(po, 'exchange_rate', 1.0) or 1.0)
    place_of_supply = getattr(supplier, 'place_of_supply', '') or ''

    # Company info
    company_name = company.name if company else 'My Company'
    company_addr = ''
    if company:
        parts = [company.address_line1, company.city, company.state]
        company_addr = ', '.join(p for p in parts if p)
    company_gstin = company.gstin if company else ''
    company_email = company.email if company else ''

    # Logo
    logo_html = ''
    if company and company.logo_url:
        logo_path = company.logo_url
        if logo_path.startswith('/static/'):
            logo_path = os.path.abspath(os.path.join(os.getcwd(), logo_path.lstrip('/')))
        # Windows path fixes
        logo_path = logo_path.replace('\\', '/')
        logo_html = f'<img src="{logo_path}" class="logo-img" />'
    else:
        logo_html = '<div style="width:60px;height:60px;background:#1a1a2e;border-radius:8px;display:flex;align-items:center;justify-content:center;color:white;font-weight:bold;font-size:12pt;text-align:center;padding-top:18px;">IMS</div>'

    # Supplier info
    supplier_name = supplier.company_name if supplier else 'N/A'
    supplier_addr = ''
    if supplier:
        parts = [supplier.address_line1, supplier.city, supplier.state, supplier.pincode]
        supplier_addr = ', '.join(p for p in parts if p)
    supplier_gstin = supplier.gstin if supplier else ''

    currency_display = f"{currency_code}"
    if currency_code == 'INR':
        currency_display = "INR (₹)"
    exchange_info = ''
    if currency_code != 'INR':
        exchange_info = f'<tr><td class="info-label">Exchange Rate</td><td>1 {currency_code} = ₹{exchange_rate:.4f}</td></tr>'

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>{_get_common_styles()}</head>
    <body>
        <table class="header-table">
            <tr>
                <td style="width:80px;">{logo_html}</td>
                <td>
                    <p class="company-name">{company_name}</p>
                    <p class="company-detail">{company_addr}</p>
                    <p class="company-detail">GSTIN: {company_gstin}</p>
                    <p class="company-detail">{company_email}</p>
                </td>
                <td style="width:40%;"><p class="doc-title">PURCHASE ORDER</p></td>
            </tr>
        </table>

        <table class="info-table">
            <tr>
                <td class="info-label">PO Number</td>
                <td>{po.po_number}</td>
                <td class="info-label">PO Date</td>
                <td>{po.order_date}</td>
            </tr>
            <tr>
                <td class="info-label">Terms</td>
                <td>Net 30</td>
                <td class="info-label">Delivery Date</td>
                <td>{po.expected_delivery_date or 'TBD'}</td>
            </tr>
            <tr>
                <td class="info-label" colspan="1">Supplier</td>
                <td colspan="1"><strong>{supplier_name}</strong></td>
                <td class="info-label">Order Currency</td>
                <td>{currency_display}</td>
            </tr>
            <tr>
                <td class="info-label">Address</td>
                <td>{supplier_addr}</td>
                <td class="info-label">Place of Supply</td>
                <td>{place_of_supply}</td>
            </tr>
            <tr>
                <td class="info-label">GSTIN</td>
                <td>{supplier_gstin}</td>
                {f'<td class="info-label">Exchange Rate</td><td>1 {currency_code} = ₹{exchange_rate:.4f}</td>' if currency_code != 'INR' else '<td></td><td></td>'}
            </tr>
        </table>

        <table class="items-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Item Description</th>
                    <th>HSN</th>
                    <th>Qty</th>
                    <th>Unit</th>
                    <th>Unit Price</th>
                    <th>Disc%</th>
                    <th>CGST</th>
                    <th>SGST</th>
                    <th>Amount</th>
                </tr>
            </thead>
            <tbody>
                {item_rows}
            </tbody>
        </table>

        <table class="totals-table">
            <tr><td class="total-label">Sub-Total</td><td class="text-right">{_format_currency(po.subtotal, currency_code)}</td></tr>
            <tr><td class="total-label">Total Discount</td><td class="text-right">{_format_currency(po.total_discount, currency_code)}</td></tr>
            {"<tr><td class='total-label'>CGST</td><td class='text-right'>" + _format_currency(po.total_cgst, currency_code) + "</td></tr>" if po.total_cgst else ""}
            {"<tr><td class='total-label'>SGST</td><td class='text-right'>" + _format_currency(po.total_sgst, currency_code) + "</td></tr>" if po.total_sgst else ""}
            {"<tr><td class='total-label'>IGST</td><td class='text-right'>" + _format_currency(po.total_igst, currency_code) + "</td></tr>" if po.total_igst else ""}
            <tr class="grand-total"><td class="total-label grand-total">Total PO Amount</td><td class="text-right grand-total">{_format_currency(po.total_amount, currency_code)}</td></tr>
        </table>

        <div class="amount-words">
            <strong>Total PO Amount in Words:</strong> {_amount_in_words(po.total_amount)}
        </div>

        <div class="notes-section">
            <strong>Notes:</strong>
            <p>{po.notes or 'N/A'}</p>
        </div>

        <div class="signature-area">
            <br/><br/><br/>
            <div class="signature-line">Authorized Purchase Signature</div>
        </div>
    </body>
    </html>
    """

    return _html_to_pdf(html)


def generate_invoice_pdf(db: Session, invoice_id: UUID) -> bytes:
    """Generate a professional Sales Invoice PDF."""
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id).first()
    if not invoice:
        raise ValueError("Invoice not found")

    customer = db.query(Customer).filter(Customer.id == invoice.customer_id).first()
    company = db.query(Company).first()
    items = db.query(SalesInvoiceItem).filter(
        SalesInvoiceItem.invoice_id == invoice.id,
        SalesInvoiceItem.is_deleted == False,
    ).all()

    # SO number
    so_number = ''
    if invoice.sales_order_id:
        so = db.query(SalesOrder).filter(SalesOrder.id == invoice.sales_order_id).first()
        if so:
            so_number = so.so_number

    # Build item rows
    item_rows = ""
    for idx, item in enumerate(items, 1):
        product = db.query(Product).filter(Product.id == item.product_id).first()
        product_name = product.name if product else "Unknown"
        hsn = product.hsn_code if product else ""
        uom = "Pcs"

        cgst_pct = float(item.gst_rate) / 2 if item.cgst_amount > 0 else 0
        sgst_pct = float(item.gst_rate) / 2 if item.sgst_amount > 0 else 0
        igst_pct = float(item.gst_rate) if item.igst_amount > 0 else 0

        tax_col = ""
        if item.igst_amount > 0:
            tax_col = f'<td class="text-right">{igst_pct:.1f}%</td><td></td>'
        else:
            tax_col = f'<td class="text-right">{cgst_pct:.1f}%</td><td class="text-right">{sgst_pct:.1f}%</td>'

        item_rows += f"""
        <tr>
            <td class="text-center">{idx}</td>
            <td class="text-left">{product_name}</td>
            <td class="text-center">{hsn}</td>
            <td class="text-right">{float(item.quantity):.2f}</td>
            <td class="text-center">{uom}</td>
            <td class="text-right">{_format_currency(item.unit_price)}</td>
            <td class="text-right">{float(item.discount_percent):.2f}</td>
            {tax_col}
            <td class="text-right">{_format_currency(item.total_amount)}</td>
        </tr>
        """

    company_name = company.name if company else 'My Company'
    company_addr = ''
    if company:
        parts = [company.address_line1, company.city, company.state]
        company_addr = ', '.join(p for p in parts if p)
    company_gstin = company.gstin if company else ''
    company_email = company.email if company else ''

    logo_html = ''
    if company and company.logo_url:
        logo_path = company.logo_url
        if logo_path.startswith('/static/'):
            logo_path = os.path.abspath(os.path.join(os.getcwd(), logo_path.lstrip('/')))
        logo_path = logo_path.replace('\\', '/')
        logo_html = f'<img src="{logo_path}" class="logo-img" />'
    else:
        logo_html = '<div style="width:60px;height:60px;background:#1a1a2e;border-radius:8px;text-align:center;padding-top:18px;color:white;font-weight:bold;font-size:12pt;">IMS</div>'

    customer_name = customer.company_name if customer else 'N/A'
    customer_addr = ''
    if customer:
        parts = [customer.billing_address_line1, customer.billing_city, customer.billing_state, customer.billing_pincode]
        customer_addr = ', '.join(p for p in parts if p)
    customer_gstin = customer.gstin if customer else ''

    # Tax headers
    if invoice.is_igst:
        tax_headers = '<th>IGST</th><th></th>'
    else:
        tax_headers = '<th>CGST</th><th>SGST</th>'

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>{_get_common_styles()}</head>
    <body>
        <table class="header-table">
            <tr>
                <td style="width:80px;">{logo_html}</td>
                <td>
                    <p class="company-name">{company_name}</p>
                    <p class="company-detail">{company_addr}</p>
                    <p class="company-detail">GSTIN: {company_gstin}</p>
                    <p class="company-detail">{company_email}</p>
                </td>
                <td style="width:40%;"><p class="doc-title">TAX INVOICE</p></td>
            </tr>
        </table>

        <table class="info-table">
            <tr>
                <td class="info-label">Invoice Number</td>
                <td>{invoice.invoice_number}</td>
                <td class="info-label">Invoice Date</td>
                <td>{invoice.invoice_date}</td>
            </tr>
            <tr>
                <td class="info-label">SO Number</td>
                <td>{so_number or 'N/A'}</td>
                <td class="info-label">Due Date</td>
                <td>{invoice.due_date or 'N/A'}</td>
            </tr>
            <tr>
                <td class="info-label">Customer</td>
                <td><strong>{customer_name}</strong></td>
                <td class="info-label">Supply State</td>
                <td>{invoice.supply_state or ''}</td>
            </tr>
            <tr>
                <td class="info-label">Address</td>
                <td>{customer_addr}</td>
                <td class="info-label">Tax Type</td>
                <td>{'IGST' if invoice.is_igst else 'CGST/SGST'}</td>
            </tr>
            <tr>
                <td class="info-label">GSTIN</td>
                <td>{customer_gstin}</td>
                <td></td><td></td>
            </tr>
        </table>

        <table class="items-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Item Description</th>
                    <th>HSN</th>
                    <th>Qty</th>
                    <th>Unit</th>
                    <th>Unit Price</th>
                    <th>Disc%</th>
                    {tax_headers}
                    <th>Amount</th>
                </tr>
            </thead>
            <tbody>
                {item_rows}
            </tbody>
        </table>

        <table class="totals-table">
            <tr><td class="total-label">Sub-Total</td><td class="text-right">{_format_currency(invoice.subtotal)}</td></tr>
            <tr><td class="total-label">Total Discount</td><td class="text-right">{_format_currency(invoice.total_discount)}</td></tr>
            {"<tr><td class='total-label'>CGST</td><td class='text-right'>" + _format_currency(invoice.total_cgst) + "</td></tr>" if invoice.total_cgst else ""}
            {"<tr><td class='total-label'>SGST</td><td class='text-right'>" + _format_currency(invoice.total_sgst) + "</td></tr>" if invoice.total_sgst else ""}
            {"<tr><td class='total-label'>IGST</td><td class='text-right'>" + _format_currency(invoice.total_igst) + "</td></tr>" if invoice.total_igst else ""}
            <tr class="grand-total"><td class="total-label grand-total">Total Invoice Amount</td><td class="text-right grand-total">{_format_currency(invoice.total_amount)}</td></tr>
        </table>

        <div class="amount-words">
            <strong>Total Amount in Words:</strong> {_amount_in_words(invoice.total_amount)}
        </div>

        <div class="notes-section">
            <strong>Notes:</strong>
            <p>{invoice.notes or 'N/A'}</p>
            <strong>Terms & Conditions:</strong>
            <p>{invoice.terms_conditions or 'N/A'}</p>
        </div>

        <div class="signature-area">
            <br/><br/><br/>
            <div class="signature-line">Authorized Signatory</div>
        </div>

        {"<p style='font-size:8pt;color:#999;margin-top:5px;text-align:center;'><em>This is a computer-generated document. No signature is required.</em></p>" if invoice.status == 'draft' else ""}
    </body>
    </html>
    """

    return _html_to_pdf(html)


def _html_to_pdf(html: str) -> bytes:
    """Convert HTML string to PDF bytes using xhtml2pdf."""
    from xhtml2pdf import pisa

    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(
        src=html,
        dest=buffer,
        encoding='utf-8',
    )
    if pisa_status.err:
        raise RuntimeError(f"PDF generation failed: {pisa_status.err}")

    buffer.seek(0)
    return buffer.read()
