"""PDF generation service using xhtml2pdf.

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
from app.models.sales import SalesInvoice, SalesInvoiceItem, SalesOrder, Quotation, QuotationItem
from app.models.supplier import Supplier


ROOT_DIR = Path(__file__).resolve().parents[2]




PO_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <title>{{ doc_title }} - {{ doc_number }}</title>
    <style>
        @page {
            size: A4;
            margin: 10mm 12mm 12mm 12mm;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: Helvetica, Arial, sans-serif;
            font-size: 10px;
            color: #000;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        td, th {
            vertical-align: top;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
    </style>
</head>
<body>

<!-- HEADER -->
<table style="table-layout: fixed; width: 100%; border-top: 1px solid #000; border-left: 1px solid #000; border-right: 1px solid #000; margin-bottom: 0;">
    <tr>
        <td style="width: 80px; vertical-align: middle; padding: 4px; border: none; text-align: center;">
            <div style="line-height: 0;">
                {% if company_logo %}
                <img src="{{ company_logo }}" alt="Logo" style="max-width: 75px; max-height: 75px; display: block; margin: 0 auto;">
                {% else %}
                <div style="width: 75px; height: 75px; background: #f9f9f9; text-align: center; line-height: 75px; font-size: 9px; color: #999; margin: 0 auto;">LOGO</div>
                {% endif %}
            </div>
        </td>
        <td style="vertical-align: top; padding: 6px 0 6px 8px; border: none;">
            <div style="font-size: 14px; font-weight: bold; margin-bottom: 3px;">{{ company_name }}</div>
            <div style="font-size: 9px; line-height: 1.4;">{{ company_address }}</div>
            <div style="font-size: 9px; line-height: 1.4;">GSTIN {{ company_gstin }}</div>
            <div style="font-size: 9px; line-height: 1.4;">{{ company_contact }}</div>
        </td>
        <td style="width: 220px; text-align: right; vertical-align: bottom; padding-bottom: 6px; padding-right: 20px; border: none;">
            <div style="font-size: 18px; font-weight: bold; letter-spacing: 1px;">PURCHASE ORDER</div>
        </td>
    </tr>
</table>

<!-- PO META DETAILS -->
<table style="table-layout: fixed; width: 100%; border: 1px solid #000;">
    <tr>
        <td style="width: 50%; border-right: 1px solid #000; padding: 4px 6px;">
            <table style="width: 100%;">
                <tr><td style="width: 85px; border: none; padding: 1px 0; font-size: 10px;">PO Number:</td><td style="border: none; padding: 1px 0; font-size: 10px; font-weight: bold;">{{ doc_number }}</td></tr>
                <tr><td style="width: 85px; border: none; padding: 1px 0; font-size: 10px;">PO Date:</td><td style="border: none; padding: 1px 0; font-size: 10px;">{{ doc_date }}</td></tr>
                <tr><td style="width: 85px; border: none; padding: 1px 0; font-size: 10px;">Terms:</td><td style="border: none; padding: 1px 0; font-size: 10px;">{{ terms }}</td></tr>
            </table>
        </td>
        <td style="width: 50%; padding: 4px 6px; vertical-align: top;">
            <table style="width: 100%;">
                <tr><td style="width: 130px; border: none; padding: 1px 0; font-size: 10px;">PO Date:</td><td style="border: none; padding: 1px 0; font-size: 10px;">{{ doc_date }}</td></tr>
                <tr><td style="width: 130px; border: none; padding: 1px 0; font-size: 10px;">Shipping/Delivery Date:</td><td style="border: none; padding: 1px 0; font-size: 10px;">{{ expected_delivery_date }}</td></tr>
                <tr><td style="width: 130px; border: none; padding: 1px 0; font-size: 10px;">Place of Supply:</td><td style="border: none; padding: 1px 0; font-size: 10px;">{{ bill_to_state }}</td></tr>
            </table>
        </td>
    </tr>
</table>

<!-- SUPPLIER & CURRENCY -->
<table style="table-layout: fixed; width: 100%; border-left: 1px solid #000; border-right: 1px solid #000; border-bottom: 1px solid #000;">
    <tr>
        <td style="width: 50%; border-right: 1px solid #000; padding: 4px 6px;">
            <div style="font-size: 10px;">Supplier: <span style="font-weight: bold;">{{ bill_to_name }}</span></div>
            <div style="font-size: 10px;">Address: {{ bill_to_address }}</div>
            <div style="font-size: 10px;">GSTIN: {{ party_gstin }}</div>
        </td>
        <td style="width: 50%; padding: 4px 6px; vertical-align: top;">
            <div style="font-size: 10px;">Order Currency:</div>
            <div style="font-size: 10px; font-weight: bold;">INR (Rs.)</div>
        </td>
    </tr>
</table>

<!-- ITEMS TABLE -->
<table style="table-layout: fixed; width: 100%; border-left: 1px solid #000; border-right: 1px solid #000; border-bottom: 1px solid #000;">
    <thead>
        <tr style="background: #f2f2f2; border-bottom: 1px solid #000;">
            <th style="width: 3%; border-right: 1px solid #000; padding: 4px 2px; text-align: center; font-size: 9px; font-weight: bold;">#</th>
            <th style="width: 28%; border-right: 1px solid #000; padding: 4px 2px; text-align: left; font-size: 9px; font-weight: bold;">Item Description</th>
            <th style="width: 9%; border-right: 1px solid #000; padding: 4px 2px; text-align: left; font-size: 9px; font-weight: bold;">Packing</th>
            <th style="width: 7%; border-right: 1px solid #000; padding: 4px 2px; text-align: right; font-size: 9px; font-weight: bold;">Qty</th>
            <th style="width: 5%; border-right: 1px solid #000; padding: 4px 2px; text-align: left; font-size: 9px; font-weight: bold;">Unit</th>
            <th style="width: 12%; border-right: 1px solid #000; padding: 4px 2px; text-align: right; font-size: 9px; font-weight: bold;">Unit Price</th>
            <th style="width: 9%; border-right: 1px solid #000; padding: 4px 2px; text-align: right; font-size: 9px; font-weight: bold;">Discount</th>
            <th style="width: 7%; border-right: 1px solid #000; padding: 4px 2px; text-align: center; font-size: 9px; font-weight: bold;">CGST</th>
            <th style="width: 7%; border-right: 1px solid #000; padding: 4px 2px; text-align: center; font-size: 9px; font-weight: bold;">SGST</th>
            <th style="width: 13%; padding: 4px 4px; text-align: right; font-size: 9px; font-weight: bold;">Amount</th>
        </tr>
    </thead>
    <tbody>
        {% for row in rows %}
        <tr>
            <td style="border-right: 1px solid #000; border-bottom: 1px solid #000; padding: 3px 2px; text-align: center; font-size: 9px;">{{ row.sr }}</td>
            <td style="border-right: 1px solid #000; border-bottom: 1px solid #000; padding: 3px 2px; text-align: left; font-size: 10px;">{{ row.description }}</td>
            <td style="border-right: 1px solid #000; border-bottom: 1px solid #000; padding: 3px 2px; text-align: left; font-size: 9px;">{{ row.packing }}</td>
            <td style="border-right: 1px solid #000; border-bottom: 1px solid #000; padding: 3px 2px; text-align: right; font-size: 9px;">{{ row.qty }}</td>
            <td style="border-right: 1px solid #000; border-bottom: 1px solid #000; padding: 3px 2px; text-align: left; font-size: 9px;">{{ row.uom }}</td>
            <td style="border-right: 1px solid #000; border-bottom: 1px solid #000; padding: 3px 2px; text-align: right; font-size: 9px;">Rs.{{ row.rate }}</td>
            <td style="border-right: 1px solid #000; border-bottom: 1px solid #000; padding: 3px 2px; text-align: right; font-size: 9px;">{{ row.disc }}</td>
            <td style="border-right: 1px solid #000; border-bottom: 1px solid #000; padding: 3px 2px; text-align: center; font-size: 9px;">{{ row.cgst_pct }}</td>
            <td style="border-right: 1px solid #000; border-bottom: 1px solid #000; padding: 3px 2px; text-align: center; font-size: 9px;">{{ row.sgst_pct }}</td>
            <td style="border-bottom: 1px solid #000; padding: 3px 4px; text-align: right; font-size: 10px;">Rs.{{ row.amount }}</td>
        </tr>
        {% endfor %}
        <!-- Spacer row -->
        <tr style="height: 200px;">
            <td style="border-right: 1px solid #000; border-bottom: none;"></td>
            <td style="border-right: 1px solid #000; border-bottom: none;"></td>
            <td style="border-right: 1px solid #000; border-bottom: none;"></td>
            <td style="border-right: 1px solid #000; border-bottom: none;"></td>
            <td style="border-right: 1px solid #000; border-bottom: none;"></td>
            <td style="border-right: 1px solid #000; border-bottom: none;"></td>
            <td style="border-right: 1px solid #000; border-bottom: none;"></td>
            <td style="border-right: 1px solid #000; border-bottom: none;"></td>
            <td style="border-right: 1px solid #000; border-bottom: none;"></td>
            <td style="border-bottom: none;"></td>
        </tr>
    </tbody>
</table>

<!-- FOOTER -->
<table style="table-layout: fixed; width: 100%; border-left: 1px solid #000; border-right: 1px solid #000; border-bottom: 1px solid #000;">
    <tr>
        <td style="width: 60%; border-right: 1px solid #000; padding: 6px 8px; vertical-align: top;">
            <div style="font-size: 9px; margin-bottom: 2px;">Total PO Amount in Words</div>
            <div style="font-size: 9.5px; font-weight: bold; font-style: italic; margin-bottom: 12px;">{{ total_in_words }}</div>
            <div style="font-size: 9px; text-decoration: underline; margin-bottom: 2px;">Notes</div>
            <div style="font-size: 9px;">{{ notes }}</div>
        </td>
        <td style="width: 40%; padding: 0; vertical-align: top;">
            <!-- Totals -->
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 3px 6px; font-size: 9.5px; border-bottom: 1px solid #000;">Sub-Total</td>
                    <td style="padding: 3px 6px; font-size: 9.5px; text-align: right; border-bottom: 1px solid #000;">Rs.{{ subtotal }}</td>
                </tr>
                <tr>
                    <td style="padding: 3px 6px; font-size: 9.5px; border-bottom: 1px solid #000;">{{ cgst_label }}</td>
                    <td style="padding: 3px 6px; font-size: 9.5px; text-align: right; border-bottom: 1px solid #000;">Rs.{{ cgst_total }}</td>
                </tr>
                <tr>
                    <td style="padding: 3px 6px; font-size: 10px; border-bottom: 1px solid #000;">{{ sgst_label }}</td>
                    <td style="padding: 3px 6px; font-size: 10px; text-align: right; border-bottom: 1px solid #000;">Rs.{{ sgst_total }}</td>
                </tr>
                {% if igst_total %}
                <tr>
                    <td style="padding: 3px 6px; font-size: 9.5px; border-bottom: 1px solid #000;">{{ igst_label }}</td>
                    <td style="padding: 3px 6px; font-size: 9.5px; text-align: right; border-bottom: 1px solid #000;">Rs.{{ igst_total }}</td>
                </tr>
                {% endif %}
                <tr>
                    <td style="padding: 4px 6px; font-size: 10px; font-weight: bold; border-bottom: 1px solid #000;">Total PO Amount</td>
                    <td style="padding: 4px 6px; font-size: 10px; font-weight: bold; text-align: right; border-bottom: 1px solid #000;">{{ grand_total_rupee }}</td>
                </tr>
            </table>
            <!-- Signature -->
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="height: 80px; text-align: center; vertical-align: bottom; border: none; padding-bottom: 5px;">
                    </td>
                </tr>
                <tr>
                    <td style="text-align: center; border: none; padding: 2px 0 8px 0; font-size: 9px;">Authorized Purchase Signature</td>
                </tr>
            </table>
        </td>
    </tr>
</table>

</body>
</html>"""

INVOICE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <title>{{ doc_title }} - {{ doc_number }}</title>
    <style>
        @page {
            size: A4;
            margin: 10mm 12mm 12mm 12mm;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: Helvetica, Arial, sans-serif;
            font-size: 10px;
            color: #000;
        }
        table {
            
            border-collapse: collapse;
        }
        td, th {
            vertical-align: top;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
    </style>
</head>
<body>

<!-- FULL PAGE BORDER WRAPPER EFFECT: 
     We apply border logic to the continuous tables. 
-->

<!-- HEADER -->
<table style="table-layout: fixed;  border-top: 1px solid #000; border-left: 1px solid #000; border-right: 1px solid #000; margin-bottom: 0;">
    <tr>
        <td style="width: 80px; vertical-align: middle; padding: 4px; border: none; text-align: center;">
            <div style="line-height: 0;">
                {% if company_logo %}
                <img src="{{ company_logo }}" alt="Logo" style="max-width: 75px; max-height: 75px; display: block; margin: 0 auto;">
                {% else %}
                <div style="width: 75px; height: 75px; background: #f9f9f9; text-align: center; line-height: 75px; font-size: 9px; color: #999; margin: 0 auto;">LOGO</div>
                {% endif %}
            </div>
        </td>
        <td style="vertical-align: top; padding: 6px 0 6px 8px; border: none;">
            <div style="font-size: 14px; font-weight: bold; margin-bottom: 3px;">{{ company_name }}</div>
            <div style="font-size: 9px; line-height: 1.4;">{{ company_address }}</div>
            <div style="font-size: 9px; line-height: 1.4;">GSTIN {{ company_gstin }}</div>
            <div style="font-size: 9px; line-height: 1.4;">{{ company_contact }}</div>
        </td>
        <td style="width: 200px; text-align: right; vertical-align: bottom; padding-bottom: 6px; padding-right: 30px; border: none;">
            <div style="font-size: 18px; font-weight: bold; letter-spacing: 1px;">{{ doc_title }}</div>
        </td>
    </tr>
</table>

<!-- META INFO -->
<table style="border: 1px solid #000;">
    <tr>
        <td style=" border-right: 1px solid #000; padding: 4px 6px;">
            <table style="">
                <tr><td style="width: 85px; border: none; padding: 1px 0; font-size: 10px;">#</td><td style="border: none; padding: 1px 0; font-size: 10px; font-weight: bold;">: {{ doc_number }}</td></tr>
                <tr><td style="width: 85px; border: none; padding: 1px 0; font-size: 10px;">Date</td><td style="border: none; padding: 1px 0; font-size: 10px; font-weight: bold;">: {{ doc_date }}</td></tr>
                {% if due_date %}<tr><td style="width: 85px; border: none; padding: 1px 0; font-size: 10px;">Due Date</td><td style="border: none; padding: 1px 0; font-size: 10px; font-weight: bold;">: {{ due_date }}</td></tr>{% endif %}
                <tr><td style="width: 85px; border: none; padding: 1px 0; font-size: 10px;">GSTIN</td><td style="border: none; padding: 1px 0; font-size: 10px; font-weight: bold;">: {{ party_gstin }}</td></tr>
            </table>
        </td>
        <td style="padding: 4px 6px; vertical-align: top;">
            <table style="">
                <tr><td style="width: 90px; border: none; padding: 1px 0; font-size: 10px;">Place Of Supply</td><td style="border: none; padding: 1px 0; font-size: 10px; font-weight: bold;">: {{ bill_to_state }}</td></tr>
            </table>
        </td>
    </tr>
</table>

<!-- ADDRESSES -->
<table style="border-left: 1px solid #000; border-right: 1px solid #000; border-bottom: 1px solid #000;">
    <tr>
        <td style=" border-right: 1px solid #000; padding: 5px 6px;">
            <div style="font-size: 9px; font-weight: bold; text-decoration: underline; margin-bottom: 3px;">Bill To</div>
            <div style="font-weight: bold; font-size: 11px; margin-bottom: 2px;">{{ bill_to_name }}</div>
            <div style="font-size: 9.5px; line-height: 1.4;">{{ bill_to_address }}<br>GSTIN {{ bill_to_gstin }}</div>
        </td>
        <td style="padding: 5px 6px;">
            <div style="font-size: 9px; font-weight: bold; text-decoration: underline; margin-bottom: 3px;">Ship To</div>
            <div style="font-weight: bold; font-size: 11px; margin-bottom: 2px;">{{ ship_to_name }}</div>
            <div style="font-size: 9.5px; line-height: 1.4;">{{ ship_to_address }}<br>GSTIN {{ ship_to_gstin }}</div>
        </td>
    </tr>
</table>

<!-- ITEMS TABLE -->
<table style="table-layout: fixed;  border-left: 1px solid #000; border-right: 1px solid #000; border-bottom: 1px solid #000;">
    
    <thead>
        <tr style="background: #f2f2f2; border-bottom: 1px solid #000;">
            <th style="width: 2%; border-right: 1px solid #000; padding: 4px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">#</th>
            <th style="width: 14%; border-right: 1px solid #000; padding: 4px 2px; text-align: center; font-size: 8px; font-weight: bold; vertical-align: middle;">Item &amp; Description</th>
            <th style="width: 6%; border-right: 1px solid #000; padding: 4px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">Pack/UoM</th>
            <th style="width: 5%; border-right: 1px solid #000; padding: 4px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">BATCH</th>
            <th style="width: 5%; border-right: 1px solid #000; padding: 4px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">MFG</th>
            <th style="width: 5%; border-right: 1px solid #000; padding: 4px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">EXP</th>
            <th style="width: 6%; border-right: 1px solid #000; padding: 4px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">HSN</th>
            <th style="width: 4%; border-right: 1px solid #000; padding: 4px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">Qty</th>
            <th style="width: 4%; border-right: 1px solid #000; padding: 4px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">Free</th>
            <th style="width: 5%; border-right: 1px solid #000; padding: 4px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">Rate</th>
            <th style="width: 5%; border-right: 1px solid #000; padding: 4px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">MRP</th>
            <th style="width: 5%; border-right: 1px solid #000; padding: 4px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">Disc.</th>
            <th style="width: 4%; border-right: 1px solid #000; padding: 4px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">CGST%</th>
            <th style="width: 6%; border-right: 1px solid #000; padding: 4px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">CGST Amt</th>
            <th style="width: 4%; border-right: 1px solid #000; padding: 4px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">SGST%</th>
            <th style="width: 6%; border-right: 1px solid #000; padding: 4px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">SGST Amt</th>
            <th style="width: 14%; padding: 4px 2px; text-align: center; font-size: 8px; font-weight: bold; vertical-align: middle;">Amount</th>
        </tr>
    </thead>
    <tbody>
        {% for row in rows %}
        <tr>
            <td style="border: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 8px;">{{ row.sr }}</td>
            <td style="border: 1px solid #000; padding: 3px 3px; text-align: left; font-size: 8.5px; font-weight: bold;">{{ row.description }}</td>
            <td style="border: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 8px;">{{ row.packing }}</td>
            <td style="border: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 8px;">{{ row.batch }}</td>
            <td style="border: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 8px;">{{ row.mfg }}</td>
            <td style="border: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 8px;">{{ row.exp }}</td>
            <td style="border: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 8px;">{{ row.hsn }}</td>
            <td style="border: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 8px;">{{ row.qty }}</td>
            <td style="border: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 8px; color: #d97706;">{{ row.free }}</td>
            <td style="border: 1px solid #000; padding: 3px 3px; text-align: right; font-size: 8px;">{{ row.rate }}</td>
            <td style="border: 1px solid #000; padding: 3px 3px; text-align: right; font-size: 8px;">{{ row.mrp }}</td>
            <td style="border: 1px solid #000; padding: 3px 3px; text-align: right; font-size: 8px;">{{ row.disc }}</td>
            <td style="border: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 8px;">{{ row.cgst_pct }}</td>
            <td style="border: 1px solid #000; padding: 3px 3px; text-align: right; font-size: 8px;">{{ row.cgst_amt }}</td>
            <td style="border: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 8px;">{{ row.sgst_pct }}</td>
            <td style="border: 1px solid #000; padding: 3px 3px; text-align: right; font-size: 8px;">{{ row.sgst_amt }}</td>
            <td style="border: 1px solid #000; padding: 3px 3px; text-align: right; font-size: 8px;">{{ row.amount }}</td>
        </tr>
        {% endfor %}
        <!-- Spacer row to push footer to bottom -->
        <tr style="height: 200px;">
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000; border-bottom: none;"></td>\n        </tr>
    </tbody>
</table>

<!-- FOOTER -->
<table style="border-left: 1px solid #000; border-right: 1px solid #000; border-bottom: 1px solid #000;">
    <tr>
        <td style=" border-right: 1px solid #000; padding: 6px 8px; vertical-align: top;">
            <div style="font-size: 9px; margin-bottom: 2px;">Total In Words</div>
            <div style="font-size: 9.5px; font-weight: bold; font-style: italic; margin-bottom: 12px;">{{ total_in_words }}</div>
            <div style="font-size: 9px; text-decoration: underline; margin-bottom: 2px;">Notes</div>
            <div style="font-size: 9px;">{{ notes }}</div>
            {% if account_holder_name or company_bank_name or company_bank_account_no or company_bank_ifsc %}
            <div style="font-size: 9px; text-decoration: underline; margin: 8px 0 2px 0;">Payment Details</div>
            {% if account_holder_name %}<div style="font-size: 9px;">Account Holder: {{ account_holder_name }}</div>{% endif %}
            {% if company_bank_name %}<div style="font-size: 9px;">Bank: {{ company_bank_name }}{% if company_bank_branch %}, {{ company_bank_branch }}{% endif %}</div>{% endif %}
            {% if company_bank_account_no %}<div style="font-size: 9px;">A/c No: {{ company_bank_account_no }}</div>{% endif %}
            {% if company_bank_ifsc %}<div style="font-size: 9px;">IFSC: {{ company_bank_ifsc }}</div>{% endif %}
            {% endif %}
        </td>
        <td style=" padding: 0; vertical-align: top;">
            <!-- Totals -->
            <table style=" border-collapse: collapse;">
                <tr>
                    <td style="padding: 3px 6px; font-size: 9.5px; border-bottom: 1px solid #000;">Sub Total</td>
                    <td style="padding: 3px 6px; font-size: 9.5px; text-align: right; border-bottom: 1px solid #000;">{{ subtotal }}</td>
                </tr>
                <tr>
                    <td style="padding: 3px 6px; font-size: 9.5px; border-bottom: 1px solid #000;">{{ cgst_label }}</td>
                    <td style="padding: 3px 6px; font-size: 9.5px; text-align: right; border-bottom: 1px solid #000;">{{ cgst_total }}</td>
                </tr>
                <tr>
                    <td style="padding: 3px 6px; font-size: 9.5px; border-bottom: 1px solid #000;">{{ sgst_label }}</td>
                    <td style="padding: 3px 6px; font-size: 9.5px; text-align: right; border-bottom: 1px solid #000;">{{ sgst_total }}</td>
                </tr>
                {% if igst_total %}
                <tr>
                    <td style="padding: 3px 6px; font-size: 9.5px; border-bottom: 1px solid #000;">{{ igst_label }}</td>
                    <td style="padding: 3px 6px; font-size: 9.5px; text-align: right; border-bottom: 1px solid #000;">{{ igst_total }}</td>
                </tr>
                {% endif %}
                <tr>
                    <td style="padding: 4px 6px; font-size: 10px; font-weight: bold; border-bottom: 1px solid #000;">Total</td>
                    <td style="padding: 4px 6px; font-size: 10px; font-weight: bold; text-align: right; border-bottom: 1px solid #000;">{{ grand_total_rupee }}</td>
                </tr>
                <tr style="background: #f2f2f2;">
                    <td style="padding: 4px 6px; font-size: 10px; font-weight: bold; border-bottom: 1px solid #000;">Balance Due</td>
                    <td style="padding: 4px 6px; font-size: 10px; font-weight: bold; text-align: right; border-bottom: 1px solid #000;">{{ balance_due_rupee }}</td>
                </tr>
            </table>
            <!-- Signature -->
            <table style=" border-collapse: collapse;">
                <tr>
                    <td style="height: 80px; text-align: center; vertical-align: bottom; border: none; padding-bottom: 5px;">
                    </td>
                </tr>
                <tr>
                    <td style="text-align: center; border: none; padding: 2px 0 8px 0; font-size: 9px;">Authorized Signature</td>
                </tr>
            </table>
        </td>
    </tr>
</table>

</body>
</html>
"""


def _build_company_address(company) -> str:
    if not company:
        return "N/A"
    parts = [
        getattr(company, "address_line1", ""),
        getattr(company, "address_line2", ""),
        getattr(company, "city", ""),
        getattr(company, "state", ""),
        getattr(company, "pincode", ""),
    ]
    formatted = ", ".join([p.strip() for p in parts if p and p.strip()])
    return formatted if formatted else "N/A"


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


def _format_currency_rupee(paise: int) -> str:
    """Format with Rs. symbol for grand total / balance due rows."""
    amount = (paise or 0) / 100
    return f"Rs.{amount:,.2f}"


def _gst_label(prefix: str, rate_pct: float) -> str:
    """Build dynamic GST label like 'CGST2.5 (2.5%)'."""
    half = rate_pct / 2
    if half == int(half):
        half_str = str(int(half))
    else:
        half_str = f"{half:.1f}"
    return f"{prefix}{half_str} ({half_str}%)"


def _decimal_to_str(value: Decimal | float | int | None) -> str:
    if value is None:
        return "0"
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def _safe_text(value: Any) -> str:
    return str(value).strip() if value is not None and str(value).strip() else "-"


def _optional_text(value: Any) -> str:
    return str(value).strip() if value is not None and str(value).strip() else ""


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
    """Convert company logo to a base64 data URI that xhtml2pdf can render."""
    import base64
    import mimetypes

    if not company or not company.logo_url:
        return None

    logo_url = str(company.logo_url)

    # Resolve to a local file path
    local_path = None
    if logo_url.startswith("/static/"):
        local_path = ROOT_DIR / logo_url.lstrip("/")
    else:
        p = Path(logo_url)
        if p.exists():
            local_path = p

    if not local_path or not local_path.exists():
        return None

    # Read the image and encode as base64 data URI
    mime_type = mimetypes.guess_type(str(local_path))[0] or "image/png"
    with open(local_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime_type};base64,{data}"


def _render_pdf(context: dict[str, Any]) -> bytes:
    html = Template(context.get("template_type", INVOICE_TEMPLATE)).render(**context)
    from xhtml2pdf import pisa
    buffer = io.BytesIO()
    status = pisa.CreatePDF(src=html, dest=buffer, encoding="utf-8")
    if status.err:
        raise RuntimeError("PDF generation failed with xhtml2pdf.")
    buffer.seek(0)
    return buffer.read()


def _layout_mode(rows: list[dict[str, str]], total_in_words: str, notes: str) -> str:
    # Retained for future template logic if needed, though unused in base template now
    return ""


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
        
        # Format rate without currency symbol for the table body to match user design expectations
        rate_val = f"{(int(item.unit_price or 0)/100):,.2f}"
        mrp_val = f"{(int(item.unit_price or 0)/100):,.2f}"
        cgst_amt_val = f"{(int(item.cgst_amount or 0)/100):,.2f}"
        sgst_amt_val = f"{(int(item.sgst_amount or 0)/100):,.2f}"
        amount_val = f"{(int(item.total_amount or 0)/100):,.2f}"

        rows.append(
            {
                "sr": str(idx),
                "description": _safe_text((item.description or (product.name if product else ""))),
                "packing": _safe_text(getattr(product, "packing", "-") if product else "-"),
                "batch": "-",
                "mfg": "-",
                "exp": "-",
                "hsn": _safe_text(product.hsn_code if product else None),
                "qty": f"{float(item.quantity):.2f}",
                "uom": "Pcs",
                "free": _decimal_to_str(getattr(item, 'free_quantity', 0)),
                "rate": rate_val,
                "mrp": mrp_val,
                "disc": f"{(int(item.discount_amount or 0)/100):.2f}",
                "cgst_pct": f"{cgst_pct}%",
                "cgst_amt": cgst_amt_val,
                "sgst_pct": f"{sgst_pct}%",
                "sgst_amt": sgst_amt_val,
                "amount": amount_val,
            }
        )

    if not rows:
        rows.append(
            {
                "sr": "1",
                "description": "-",
                "packing": "-",
                "batch": "-",
                "mfg": "-",
                "exp": "-",
                "hsn": "-",
                "qty": "0.00",
                "uom": "Pcs",
                "free": "0",
                "rate": "0.00",
                "mrp": "0.00",
                "disc": "0.00",
                "cgst_pct": "0.0%",
                "cgst_amt": "0.00",
                "sgst_pct": "0.0%",
                "sgst_amt": "0.00",
                "amount": "0.00",
            }
        )

    notes_text = _safe_text(po.notes)
    total_words = _amount_in_words(int(po.total_amount or 0))

    # Determine dominant GST rate from items for label
    dominant_gst = 0.0
    for item in items:
        r = float(item.gst_rate or 0)
        if r > dominant_gst:
            dominant_gst = r

    supplier_address = _safe_text(
        ", ".join(
            [p.strip() for p in [supplier.address_line1 if supplier else None, supplier.address_line2 if supplier else None, supplier.city if supplier else None, supplier.state if supplier else None, supplier.pincode if supplier else None] if p and p.strip()]
        )
    )

    context = {
        "template_type": PO_TEMPLATE,
        "doc_title": "PURCHASE ORDER",
        "doc_number": _safe_text(po.po_number),
        "doc_date": _format_date(po.order_date),
        "expected_delivery_date": _format_date(po.expected_delivery_date) if po.expected_delivery_date else "-",
        "terms": "Net 30",
        "company_logo": _resolve_logo_src(company),
        "company_name": _safe_text(company.name if company else None),
        "company_address": _build_company_address(company),
        "company_gstin": _safe_text(company.gstin if company else None),
        "company_contact": _safe_text(company.phone if company and company.phone else (company.email if company else None)),
        "party_gstin": _safe_text(supplier.gstin if supplier else None),
        "bill_to_state": _safe_text(supplier.state if supplier else None),
        "bill_to_name": _safe_text(supplier.company_name if supplier else None),
        "bill_to_address": supplier_address,
        "rows": rows,
        "subtotal": f"{(int(po.subtotal or 0)/100):,.2f}",
        "cgst_label": _gst_label("CGST", dominant_gst) if dominant_gst else "CGST Total",
        "cgst_total": f"{(int(po.total_cgst or 0)/100):,.2f}",
        "sgst_label": _gst_label("SGST", dominant_gst) if dominant_gst else "SGST Total",
        "sgst_total": f"{(int(po.total_sgst or 0)/100):,.2f}",
        "igst_label": _gst_label("IGST", dominant_gst) if dominant_gst else "IGST Total",
        "igst_total": f"{(int(po.total_igst or 0)/100):,.2f}" if int(po.total_igst or 0) else "",
        "grand_total_rupee": _format_currency_rupee(int(po.total_amount or 0)),
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
        
        rate_val = f"{(int(item.unit_price or 0)/100):,.2f}"
        mrp_val = f"{(int(item.mrp or item.unit_price or 0)/100):,.2f}"
        cgst_amt_val = f"{(int(item.cgst_amount or 0)/100):,.2f}"
        sgst_amt_val = f"{(int(item.sgst_amount or 0)/100):,.2f}"
        amount_val = f"{(int(item.total_amount or 0)/100):,.2f}"

        rows.append(
            {
                "sr": str(idx),
                "description": _safe_text((item.description or (product.name if product else ""))),
                "packing": _safe_text(getattr(product, "packing", "-") if product else "-"),
                "batch": "-",
                "mfg": "-",
                "exp": "-",
                "hsn": _safe_text(product.hsn_code if product else None),
                "qty": f"{float(item.quantity):.2f}",
                "free": _decimal_to_str(getattr(item, 'free_quantity', 0)),
                "uom": "Pcs", # You can map this dynamically to product.uom if needed
                "rate": rate_val,
                "mrp": mrp_val,
                "disc": f"{(int(item.discount_amount or 0)/100):.2f}",
                "cgst_pct": f"{cgst_pct}%",
                "sgst_pct": f"{sgst_pct}%",
                "cgst_amt": cgst_amt_val,
                "sgst_amt": sgst_amt_val,
                "amount": amount_val,
            }
        )

    if not rows:
        rows.append(
            {
                "sr": "1",
                "description": "-",
                "packing": "-",
                "batch": "-",
                "mfg": "-",
                "exp": "-",
                "hsn": "-",
                "qty": "0.00",
                "free": "0",
                "uom": "Pcs",
                "rate": "0.00",
                "mrp": "0.00",
                "disc": "0.00",
                "cgst_pct": "0.0%",
                "sgst_pct": "0.0%",
                "cgst_amt": "0.00",
                "sgst_amt": "0.00",
                "amount": "0.00",
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

    # Determine dominant GST rate from items for label
    dominant_gst = 0.0
    for item in items:
        r = float(item.gst_rate or 0)
        if r > dominant_gst:
            dominant_gst = r

    # Balance due = total - paid
    balance_due_paise = int(invoice.amount_due or invoice.total_amount or 0)

    context = {
        "doc_title": "TAX INVOICE",
        "doc_number": _safe_text(invoice.invoice_number),
        "doc_date": _format_date(invoice.invoice_date),
        "due_date": _format_date(invoice.due_date) if invoice.due_date else "",
        "company_logo": _resolve_logo_src(company),
        "company_name": _safe_text(company.name if company else None),
        "company_address": _build_company_address(company),
        "company_gstin": _safe_text(company.gstin if company else None),
        "company_contact": _safe_text(company.phone if company and company.phone else (company.email if company else None)),
        "account_holder_name": _optional_text(company.account_holder_name if company else None),
        "company_bank_name": _optional_text(company.bank_name if company else None),
        "company_bank_account_no": _optional_text(company.bank_account_no if company else None),
        "company_bank_ifsc": _optional_text(company.bank_ifsc if company else None),
        "company_bank_branch": _optional_text(company.bank_branch if company else None),
        "party_gstin": _safe_text(customer.gstin if customer else None),
        "bill_to_state": _safe_text(customer.billing_state if customer else None),
        "bill_to_name": _safe_text(customer.company_name if customer else None),
        "bill_to_address": _safe_text(", ".join([p.strip() for p in billing_parts if p and p.strip()])),
        "bill_to_gstin": _safe_text(customer.gstin if customer else None),
        "ship_to_name": _safe_text(customer.company_name if customer else None),
        "ship_to_address": _safe_text(ship_to_address),
        "ship_to_gstin": _safe_text(customer.gstin if customer else None),
        "rows": rows,
        "subtotal": _format_currency(int(invoice.subtotal or 0), "INR"),
        "cgst_label": _gst_label("CGST", dominant_gst) if dominant_gst else "CGST Total",
        "cgst_total": _format_currency(int(invoice.total_cgst or 0), "INR"),
        "sgst_label": _gst_label("SGST", dominant_gst) if dominant_gst else "SGST Total",
        "sgst_total": _format_currency(int(invoice.total_sgst or 0), "INR"),
        "igst_label": _gst_label("IGST", dominant_gst) if dominant_gst else "IGST Total",
        "igst_total": _format_currency(int(invoice.total_igst or 0), "INR") if int(invoice.total_igst or 0) else "",
        "grand_total_rupee": _format_currency_rupee(int(invoice.total_amount or 0)),
        "balance_due_rupee": _format_currency_rupee(balance_due_paise),
        "total_in_words": total_words,
        "notes": notes_text,
    }
    return _render_pdf(context)


def generate_quotation_pdf(db: Session, quotation_id: UUID) -> bytes:
    """Generate Quotation PDF in the same print format as invoice template."""
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise ValueError("Quotation not found")

    company = db.query(Company).first()
    customer = db.query(Customer).filter(Customer.id == quotation.customer_id).first()
    items = (
        db.query(QuotationItem)
        .filter(QuotationItem.quotation_id == quotation.id, QuotationItem.is_deleted == False)
        .all()
    )

    rows: list[dict[str, str]] = []
    for idx, item in enumerate(items, start=1):
        product = db.query(Product).filter(Product.id == item.product_id).first()
        gst_rate = int(item.gst_rate or 0)
        cgst_pct = f"{gst_rate / 2:.1f}" if item.cgst_amount else "0"
        sgst_pct = f"{gst_rate / 2:.1f}" if item.sgst_amount else "0"

        rate_val = f"{(int(item.unit_price or 0)/100):,.2f}"
        mrp_source = int(getattr(product, "mrp", item.unit_price) or item.unit_price or 0)
        mrp_val = f"{(mrp_source/100):,.2f}"
        cgst_amt_val = f"{(int(item.cgst_amount or 0)/100):,.2f}"
        sgst_amt_val = f"{(int(item.sgst_amount or 0)/100):,.2f}"
        amount_val = f"{(int(item.total_amount or 0)/100):,.2f}"

        rows.append(
            {
                "sr": str(idx),
                "description": _safe_text((item.description or (product.name if product else ""))),
                "packing": _safe_text(getattr(product, "packing", "-") if product else "-"),
                "batch": "-",
                "mfg": "-",
                "exp": "-",
                "hsn": _safe_text(product.hsn_code if product else None),
                "qty": f"{float(item.quantity):.2f}",
                "free": "0",
                "uom": "Pcs",
                "rate": rate_val,
                "mrp": mrp_val,
                "disc": f"{(int(item.discount_amount or 0)/100):.2f}",
                "cgst_pct": f"{cgst_pct}%",
                "sgst_pct": f"{sgst_pct}%",
                "cgst_amt": cgst_amt_val,
                "sgst_amt": sgst_amt_val,
                "amount": amount_val,
            }
        )

    if not rows:
        rows.append(
            {
                "sr": "1",
                "description": "-",
                "packing": "-",
                "batch": "-",
                "mfg": "-",
                "exp": "-",
                "hsn": "-",
                "qty": "0.00",
                "free": "0",
                "uom": "Pcs",
                "rate": "0.00",
                "mrp": "0.00",
                "disc": "0.00",
                "cgst_pct": "0.0%",
                "sgst_pct": "0.0%",
                "cgst_amt": "0.00",
                "sgst_amt": "0.00",
                "amount": "0.00",
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

    valid_until_text = _format_date(quotation.valid_until) if quotation.valid_until else "-"
    notes_text = _safe_text(quotation.notes) if quotation.notes else "-"
    notes_text = f"Valid Until: {valid_until_text}\n{notes_text}" if notes_text != "-" else f"Valid Until: {valid_until_text}"
    total_words = _amount_in_words(int(quotation.total_amount or 0))

    dominant_gst = 0.0
    for item in items:
        r = float(item.gst_rate or 0)
        if r > dominant_gst:
            dominant_gst = r

    context = {
        "doc_title": "QUOTATION",
        "doc_number": _safe_text(quotation.quotation_number),
        "doc_date": _format_date(quotation.quotation_date),
        "due_date": "",
        "company_logo": _resolve_logo_src(company),
        "company_name": _safe_text(company.name if company else None),
        "company_address": _build_company_address(company),
        "company_gstin": _safe_text(company.gstin if company else None),
        "company_contact": _safe_text(company.phone if company and company.phone else (company.email if company else None)),
        "account_holder_name": _optional_text(company.account_holder_name if company else None),
        "company_bank_name": _optional_text(company.bank_name if company else None),
        "company_bank_account_no": _optional_text(company.bank_account_no if company else None),
        "company_bank_ifsc": _optional_text(company.bank_ifsc if company else None),
        "company_bank_branch": _optional_text(company.bank_branch if company else None),
        "party_gstin": _safe_text(customer.gstin if customer else None),
        "bill_to_state": _safe_text(customer.billing_state if customer else None),
        "bill_to_name": _safe_text(customer.company_name if customer else None),
        "bill_to_address": _safe_text(", ".join([p.strip() for p in billing_parts if p and p.strip()])),
        "bill_to_gstin": _safe_text(customer.gstin if customer else None),
        "ship_to_name": _safe_text(customer.company_name if customer else None),
        "ship_to_address": _safe_text(ship_to_address),
        "ship_to_gstin": _safe_text(customer.gstin if customer else None),
        "rows": rows,
        "subtotal": _format_currency(int(quotation.subtotal or 0), "INR"),
        "cgst_label": _gst_label("CGST", dominant_gst) if dominant_gst else "CGST Total",
        "cgst_total": _format_currency(int(quotation.total_cgst or 0), "INR"),
        "sgst_label": _gst_label("SGST", dominant_gst) if dominant_gst else "SGST Total",
        "sgst_total": _format_currency(int(quotation.total_sgst or 0), "INR"),
        "igst_label": _gst_label("IGST", dominant_gst) if dominant_gst else "IGST Total",
        "igst_total": _format_currency(int(quotation.total_igst or 0), "INR") if int(quotation.total_igst or 0) else "",
        "grand_total_rupee": _format_currency_rupee(int(quotation.total_amount or 0)),
        "balance_due_rupee": _format_currency_rupee(int(quotation.total_amount or 0)),
        "total_in_words": total_words,
        "notes": notes_text,
    }
    return _render_pdf(context)
