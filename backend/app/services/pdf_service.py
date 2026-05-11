"""PDF generation service using xhtml2pdf.

Generates GST-compliant Purchase Order and Tax Invoice PDFs with a
single-page-optimized A4 layout using Jinja-style HTML templates.
"""

from __future__ import annotations

import base64
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
from app.models.product import Product, UnitOfMeasure
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.sales import SalesInvoice, SalesInvoiceItem, SalesOrder, Quotation, QuotationItem
from app.models.supplier import Supplier
from app.services.gst_service import determine_default_invoice_type, determine_tax_mode, is_india_country
from app.utils.rounding import round_paise_to_nearest_5


ROOT_DIR = Path(__file__).resolve().parents[2]
BILLING_PDF_ITEMS_PER_PAGE = 15
AMBASSADOR_WATERMARK_OPACITY = 0.18
AMBASSADOR_WATERMARK_MAX_WIDTH_PT = 280.0
AMBASSADOR_WATERMARK_PAGE_WIDTH_RATIO = 0.52


PO_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <title>{{ doc_title }} - {{ doc_number }}</title>
    <style>
        @page {
            size: A4;
            margin: 10mm 12mm 12mm 12mm;
            @frame footer {
                -pdf-frame-content: footer-content;
                bottom: 10mm;
                margin-left: 12mm;
                margin-right: 12mm;
                height: 10mm;
            }
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: Helvetica, Arial, sans-serif;
            font-size: 10px;
            color: #000;
        }
        .content-layer {
            position: relative;
            min-height: 255mm;
        }
        .content-foreground {
            position: relative;
            z-index: 1;
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
        tr {
            page-break-inside: avoid;
        }
        .page-break {
            page-break-after: always;
        }
        .po-watermark {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%) rotate(-24deg);
            font-size: 42px;
            font-weight: 700;
            color: #b9c0ca;
            opacity: 0.14;
            letter-spacing: 1px;
            z-index: 30;
            white-space: nowrap;
        }
    </style>
</head>
<body>

<div class="po-watermark">{{ watermark_text }}</div>

<div class="content-layer">
<div class="content-foreground">

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
                <tr><td style="width: 85px; border: none; padding: 1px 0; font-size: 10px;">Payment Terms:</td><td style="border: none; padding: 1px 0; font-size: 10px;">{{ terms }}</td></tr>
            </table>
        </td>
        <td style="width: 50%; padding: 4px 6px; vertical-align: top;">
            <table style="width: 100%;">
                <tr><td style="width: 130px; border: none; padding: 1px 0; font-size: 10px;">PO Date:</td><td style="border: none; padding: 1px 0; font-size: 10px;">{{ doc_date }}</td></tr>
                <tr><td style="width: 130px; border: none; padding: 1px 0; font-size: 10px;">Shipping/Delivery Date:</td><td style="border: none; padding: 1px 0; font-size: 10px;">{{ expected_delivery_date }}</td></tr>
                <tr><td style="width: 130px; border: none; padding: 1px 0; font-size: 10px;">Place of Supply:</td><td style="border: none; padding: 1px 0; font-size: 10px;">{{ place_of_supply }}</td></tr>
                <tr><td style="width: 130px; border: none; padding: 1px 0; font-size: 10px;">Under Delivery Tol.:</td><td style="border: none; padding: 1px 0; font-size: 10px;">{{ under_delivery_tolerance }}</td></tr>
                <tr><td style="width: 130px; border: none; padding: 1px 0; font-size: 10px;">Over Delivery Tol.:</td><td style="border: none; padding: 1px 0; font-size: 10px;">{{ over_delivery_tolerance }}</td></tr>
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
            <div style="font-size: 10px; font-weight: bold;">{{ order_currency }}</div>
        </td>
    </tr>
</table>

<!-- ITEMS TABLE -->
<table style="table-layout: fixed; width: 100%; border-left: 1px solid #000; border-right: 1px solid #000; border-bottom: 1px solid #000;">
    <thead>
        <tr style="background: #f2f2f2; border-bottom: 1px solid #000;">
            <th style="width: 4%; border-right: 1px solid #000; padding: 4px 2px; text-align: center; font-size: 9px; font-weight: bold;">S.No</th>
            <th style="width: 28%; border-right: 1px solid #000; padding: 4px 2px; text-align: left; font-size: 9px; font-weight: bold;">Item Description</th>
            <th style="width: 9%; border-right: 1px solid #000; padding: 4px 2px; text-align: left; font-size: 9px; font-weight: bold;">Packing / Order Unit</th>
            <th style="width: 7%; border-right: 1px solid #000; padding: 4px 2px; text-align: right; font-size: 9px; font-weight: bold;">Qty</th>
            <th style="width: 5%; border-right: 1px solid #000; padding: 4px 2px; text-align: left; font-size: 9px; font-weight: bold;">Base Unit</th>
            <th style="width: 12%; border-right: 1px solid #000; padding: 4px 2px; text-align: right; font-size: 9px; font-weight: bold;">Unit Price</th>
            <th style="width: 9%; border-right: 1px solid #000; padding: 4px 2px; text-align: right; font-size: 9px; font-weight: bold;">Discount</th>
            {% if show_igst %}
            <th style="width: 14%; border-right: 1px solid #000; padding: 4px 2px; text-align: center; font-size: 9px; font-weight: bold;">IGST</th>
            {% else %}
            <th style="width: 7%; border-right: 1px solid #000; padding: 4px 2px; text-align: center; font-size: 9px; font-weight: bold;">{{ cgst_column_label }}</th>
            <th style="width: 7%; border-right: 1px solid #000; padding: 4px 2px; text-align: center; font-size: 9px; font-weight: bold;">{{ tax_secondary_column_label }}</th>
            {% endif %}
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
            <td style="border-right: 1px solid #000; border-bottom: 1px solid #000; padding: 3px 2px; text-align: right; font-size: 9px;">{{ cs }}{{ row.rate }}</td>
            <td style="border-right: 1px solid #000; border-bottom: 1px solid #000; padding: 3px 2px; text-align: right; font-size: 9px;">{{ row.disc }}</td>
            {% if show_igst %}
            <td style="border-right: 1px solid #000; border-bottom: 1px solid #000; padding: 3px 2px; text-align: center; font-size: 9px;">{{ row.igst_pct }}</td>
            {% else %}
            <td style="border-right: 1px solid #000; border-bottom: 1px solid #000; padding: 3px 2px; text-align: center; font-size: 9px;">{{ row.cgst_pct }}</td>
            <td style="border-right: 1px solid #000; border-bottom: 1px solid #000; padding: 3px 2px; text-align: center; font-size: 9px;">{{ row.sgst_pct }}</td>
            {% endif %}
            <td style="border-bottom: 1px solid #000; padding: 3px 4px; text-align: right; font-size: 10px;">{{ cs }}{{ row.amount }}</td>
        </tr>
        {% endfor %}
        <!-- Spacer row -->
        <tr style="height: {% if rows|length < items_per_page %}120px{% else %}12px{% endif %};">
            <td style="border-right: 1px solid #000;"></td>
            <td style="border-right: 1px solid #000;"></td>
            <td style="border-right: 1px solid #000;"></td>
            <td style="border-right: 1px solid #000;"></td>
            <td style="border-right: 1px solid #000;"></td>
            <td style="border-right: 1px solid #000;"></td>
            <td style="border-right: 1px solid #000;"></td>
            {% if show_igst %}
            <td style="border-right: 1px solid #000;"></td>
            {% else %}
            <td style="border-right: 1px solid #000;"></td>
            <td style="border-right: 1px solid #000;"></td>
            {% endif %}
            <td></td>
        </tr>
    </tbody>
</table>

<!-- FOOTER -->
{% if is_last_page %}
<table style="table-layout: fixed; width: 100%; border-left: 1px solid #000; border-right: 1px solid #000; border-bottom: 1px solid #000;">
    <tr>
        <td style="width: 60%; border-right: 1px solid #000; padding: 6px 8px; vertical-align: top;">
            <div style="font-size: 9px; margin-bottom: 2px;">Total PO Amount in Words</div>
            <div style="font-size: 9.5px; font-weight: bold; font-style: italic; margin-bottom: 12px;">{{ total_in_words }}</div>
            <div style="font-size: 9px; text-decoration: underline; margin-bottom: 2px;">Notes</div>
            <div style="font-size: 9px;">{{ notes }}</div>
        </td>
        <td style="width: 40%; padding: 0; vertical-align: top;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 3px 6px; font-size: 9.5px; border-bottom: 1px solid #000;">Sub-Total</td>
                    <td style="padding: 3px 6px; font-size: 9.5px; text-align: right; border-bottom: 1px solid #000;">{{ subtotal }}</td>
                </tr>
                {% if gst_applicable and show_igst %}
                <tr>
                    <td style="padding: 3px 6px; font-size: 9.5px; border-bottom: 1px solid #000;">{{ igst_label }}</td>
                    <td style="padding: 3px 6px; font-size: 9.5px; text-align: right; border-bottom: 1px solid #000;">{{ igst_total }}</td>
                </tr>
                {% elif gst_applicable %}
                <tr>
                    <td style="padding: 3px 6px; font-size: 9.5px; border-bottom: 1px solid #000;">{{ cgst_label }}</td>
                    <td style="padding: 3px 6px; font-size: 9.5px; text-align: right; border-bottom: 1px solid #000;">{{ cgst_total }}</td>
                </tr>
                <tr>
                    <td style="padding: 3px 6px; font-size: 10px; border-bottom: 1px solid #000;">{{ sgst_label }}</td>
                    <td style="padding: 3px 6px; font-size: 10px; text-align: right; border-bottom: 1px solid #000;">{{ sgst_total }}</td>
                </tr>
                {% endif %}
                <tr>
                    <td style="padding: 4px 6px; font-size: 10px; font-weight: bold; border-bottom: 1px solid #000;">Total PO Amount</td>
                    <td style="padding: 4px 6px; font-size: 10px; font-weight: bold; text-align: right; border-bottom: 1px solid #000;">{{ grand_total_rupee }}</td>
                </tr>
            </table>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="height: 60px; text-align: center; vertical-align: bottom; border: none; padding-bottom: 5px;"></td>
                </tr>
                <tr>
                    <td style="text-align: center; border: none; padding: 2px 0 0 0; font-size: 8px; font-weight: 600; white-space: nowrap;">For {{ company_name }}</td>
                </tr>
                <tr>
                    <td style="text-align: center; border: none; padding: 2px 0 8px 0; font-size: 9px;">Authorized Purchase Signature</td>
                </tr>
            </table>
        </td>
    </tr>
</table>
{% else %}
<table style="table-layout: fixed; width: 100%; border-left: 1px solid #000; border-right: 1px solid #000; border-bottom: 1px solid #000;">
    <tr>
        <td style="width: 100%; padding: 40px 8px 6px 8px; vertical-align: bottom; text-align: right; font-size: 9px; color: #666;">
            <em>Continued on next page...</em>
        </td>
    </tr>
</table>
{% endif %}

<div id="footer-content" style="text-align: center; font-size: 9px; color: #666; padding-top: 4px;">
    Page {{ current_page }} of {{ total_pages }}
</div>

</div>
</div>

</body>
</html>
"""


INVOICE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <title>{{ doc_title }} - {{ doc_number }}</title>
    <style>
        @page {
            size: A4;
            margin: 10mm 12mm 12mm 12mm;
            @frame footer {
                -pdf-frame-content: footer-content;
                bottom: 10mm;
                margin-left: 12mm;
                margin-right: 12mm;
                height: 10mm;
            }
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: Helvetica, Arial, sans-serif;
            font-size: 10px;
            color: #000;
        }
        .content-layer {
            position: relative;
            min-height: 255mm;
        }
        .content-foreground {
            position: relative;
            z-index: 1;
        }
        table {
            border-collapse: collapse;
        }
        td, th {
            vertical-align: top;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
        tr {
            page-break-inside: avoid;
        }
        .po-watermark {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%) rotate(-24deg);
            font-size: 42px;
            font-weight: 700;
            color: #b9c0ca;
            opacity: 0.14;
            letter-spacing: 1px;
            z-index: 30;
            white-space: nowrap;
        }
    </style>
</head>
<body>

<div class="po-watermark">{{ watermark_text }}</div>

<div class="content-layer">
<div class="content-foreground">

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
            {% if export_invoice and company_import_export_number %}
            <div style="font-size: 9px; line-height: 1.4;">Import &amp; Export Number: {{ company_import_export_number }}</div>
            {% endif %}
        </td>
        <td style="width: 200px; text-align: right; vertical-align: bottom; padding-bottom: 6px; padding-right: 30px; border: none;">
            <div style="font-size: 18px; font-weight: bold; letter-spacing: 1px;">{{ doc_title }}</div>
        </td>
    </tr>
</table>

<!-- META INFO -->
<table style="width: 100%; border: 1px solid #000;">
    <tr>
        <td style="width: 50%; border-right: 1px solid #000; padding: 4px 6px;">
            <table style="width: 100%;">
                <tr><td style="width: 110px; border: none; padding: 1px 0; font-size: 10px;">{{ doc_number_label }}</td><td style="border: none; padding: 1px 0; font-size: 10px; font-weight: bold;">: {{ doc_number }}</td></tr>
                <tr><td style="width: 85px; border: none; padding: 1px 0; font-size: 10px;">{{ doc_date_label }}</td><td style="border: none; padding: 1px 0; font-size: 10px; font-weight: bold;">: {{ doc_date }}</td></tr>
                <tr><td style="width: 85px; border: none; padding: 1px 0; font-size: 10px;">Due Date</td><td style="border: none; padding: 1px 0; font-size: 10px; font-weight: bold;">: {{ due_date }}</td></tr>
                <tr><td style="width: 85px; border: none; padding: 1px 0; font-size: 10px;">Payment Terms</td><td style="border: none; padding: 1px 0; font-size: 10px; font-weight: bold;">: {{ payment_terms }}</td></tr>
            </table>
        </td>
        <td style="width: 50%; padding: 4px 6px; vertical-align: top;">
            <table style="width: 100%;">
                <tr><td style="width: 90px; border: none; padding: 1px 0; font-size: 10px;">Invoice Type</td><td style="border: none; padding: 1px 0; font-size: 10px; font-weight: bold;">: {{ invoice_type_label }}</td></tr>
                <tr><td style="width: 90px; border: none; padding: 1px 0; font-size: 10px;">Place Of Supply</td><td style="border: none; padding: 1px 0; font-size: 10px; font-weight: bold;">: {{ place_of_supply }}</td></tr>
                {% if order_currency %}<tr><td style="width: 90px; border: none; padding: 1px 0; font-size: 10px;">Order Currency</td><td style="border: none; padding: 1px 0; font-size: 10px; font-weight: bold;">: {{ order_currency }}</td></tr>{% endif %}
                {% if export_invoice and import_export_code %}<tr><td style="width: 120px; border: none; padding: 1px 0; font-size: 10px;">Import &amp; Export Code</td><td style="border: none; padding: 1px 0; font-size: 10px; font-weight: bold;">: {{ import_export_code }}</td></tr>{% endif %}
            </table>
        </td>
    </tr>
</table>

<!-- ADDRESSES -->
<table style="width: 100%; border-left: 1px solid #000; border-right: 1px solid #000; border-bottom: 1px solid #000;">
    <tr>
        <td style="width: 50%; border-right: 1px solid #000; padding: 5px 6px;">
            <div style="font-size: 9px; font-weight: bold; text-decoration: underline; margin-bottom: 3px;">Bill To</div>
            <div style="font-weight: bold; font-size: 11px; margin-bottom: 2px;">{{ bill_to_name }}</div>
            <div style="font-size: 9.5px; line-height: 1.4;">
                {{ bill_to_address }}
                {% if not export_invoice and bill_to_gstin and bill_to_gstin != '-' %}<br>GSTIN {{ bill_to_gstin }}{% endif %}
            </div>
        </td>
        <td style="width: 50%; padding: 5px 6px;">
            <div style="font-size: 9px; font-weight: bold; text-decoration: underline; margin-bottom: 3px;">Ship To</div>
            <div style="font-weight: bold; font-size: 11px; margin-bottom: 2px;">{{ ship_to_name }}</div>
            <div style="font-size: 9.5px; line-height: 1.4;">
                {{ ship_to_address }}
                {% if not export_invoice and ship_to_gstin and ship_to_gstin != '-' %}<br>GSTIN {{ ship_to_gstin }}{% endif %}
            </div>
        </td>
    </tr>
</table>

<!-- ITEMS TABLE -->
{% if export_invoice %}
<table style="table-layout: fixed; width: 100%; border-left: 1px solid #000; border-right: 1px solid #000; border-bottom: 1px solid #000;">
    <thead>
        <tr style="background: #f2f2f2; border-bottom: 1px solid #000;">
            <th style="width: 10%; border-right: 1px solid #000; padding: 4px 2px; text-align: center; font-size: 9px; font-weight: bold;">S.No</th>
            <th style="width: 50%; border-right: 1px solid #000; padding: 4px 2px; text-align: center; font-size: 9px; font-weight: bold;">Description</th>
            <th style="width: 25%; border-right: 1px solid #000; padding: 4px 2px; text-align: center; font-size: 9px; font-weight: bold;">Amount</th>
            <th style="width: 15%; padding: 4px 2px; text-align: center; font-size: 9px; font-weight: bold;">Currency</th>
        </tr>
    </thead>
    <tbody>
        {% for row in rows %}
        <tr>
            <td style="border: 1px solid #000; padding: 3px 2px; text-align: center; font-size: 9px;">{{ row.sr }}</td>
            <td style="border: 1px solid #000; padding: 3px 4px; text-align: left; font-size: 9px; word-wrap: break-word; overflow-wrap: break-word;">{{ row.description }}</td>
            <td style="border: 1px solid #000; padding: 3px 4px; text-align: right; font-size: 9px; font-weight: bold;">{{ row.amount }}</td>
            <td style="border: 1px solid #000; padding: 3px 2px; text-align: center; font-size: 9px;">{{ raw_currency }}</td>
        </tr>
        {% endfor %}
        <!-- Spacer row -->
        <tr style="height: {% if rows|length < items_per_page %}120px{% else %}12px{% endif %};">
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
        </tr>
    </tbody>
</table>
{% else %}
{% if show_batch_columns %}
    {% if export_invoice %}
        {% set col_sr = 3 %}
        {% set col_desc = 18 %}
        {% set col_base = 5 %}
        {% set col_pack = 5 %}
        {% set col_batch = 8 %}
        {% set col_mfg = 7 %}
        {% set col_exp = 7 %}
        {% set col_hsn = 6 %}
        {% set col_qty = 7 %}
        {% set col_free = 4 %}
        {% set col_rate = 11 %}
        {% set col_disc = 5 %}
        {% set col_cgst = 0 %}
        {% set col_sgst = 0 %}
        {% set col_amount = 14 %}
    {% else %}
        {% set col_sr = 3 %}
        {% set col_desc = 13 %}
        {% set col_base = 5 %}
        {% set col_pack = 5 %}
        {% set col_batch = 8 %}
        {% set col_mfg = 7 %}
        {% set col_exp = 7 %}
        {% set col_hsn = 6 %}
        {% set col_qty = 5 %}
        {% set col_free = 4 %}
        {% set col_rate = 8 %}
        {% set col_disc = 5 %}
        {% set col_cgst = 7 %}
        {% set col_sgst = 7 %}
        {% set col_amount = 10 %}
    {% endif %}
{% else %}
    {% if export_invoice %}
        {% set col_sr = 3 %}
        {% set col_desc = 29 %}
        {% set col_base = 6 %}
        {% set col_pack = 6 %}
        {% set col_hsn = 8 %}
        {% set col_qty = 8 %}
        {% set col_free = 5 %}
        {% set col_rate = 11 %}
        {% set col_disc = 6 %}
        {% set col_cgst = 0 %}
        {% set col_sgst = 0 %}
        {% set col_amount = 18 %}
    {% else %}
        {% set col_sr = 3 %}
        {% set col_desc = 19 %}
        {% set col_base = 6 %}
        {% set col_pack = 6 %}
        {% set col_hsn = 8 %}
        {% set col_qty = 7 %}
        {% set col_free = 5 %}
        {% set col_rate = 10 %}
        {% set col_disc = 6 %}
        {% set col_cgst = 8 %}
        {% set col_sgst = 8 %}
        {% set col_amount = 14 %}
    {% endif %}
{% endif %}

<table style="table-layout: fixed; width: 100%; border-left: 1px solid #000; border-right: 1px solid #000; border-bottom: 1px solid #000;">
    <thead>
        <tr style="background: #f2f2f2; border-bottom: 1px solid #000;">
            <th style="width: {{ col_sr }}%; border-right: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">Sr</th>
            <th style="width: {{ col_desc }}%; border-right: 1px solid #000; padding: 3px 2px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">Item &amp; Description</th>
            <th style="width: {{ col_base }}%; border-right: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">{{ unit_col_label }}</th>
            <th style="width: {{ col_pack }}%; border-right: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">Packing / Order Unit</th>
            {% if show_batch_columns %}
            <th style="width: {{ col_batch }}%; border-right: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">Batch No</th>
            <th style="width: {{ col_mfg }}%; border-right: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">MFG Date</th>
            <th style="width: {{ col_exp }}%; border-right: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">EXP Date</th>
            {% endif %}
            <th style="width: {{ col_hsn }}%; border-right: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">HSN</th>
            <th style="width: {{ col_qty }}%; border-right: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">Qty</th>
            <th style="width: {{ col_free }}%; border-right: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">Free</th>
            <th style="width: {{ col_rate }}%; border-right: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">Rate</th>
            <th style="width: {{ col_disc }}%; border-right: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">Disc%</th>
            {% if not export_invoice %}
                {% if show_igst %}
            <th style="width: {{ col_cgst + col_sgst }}%; border-right: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">IGST</th>
                {% else %}
            <th style="width: {{ col_cgst }}%; border-right: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">{{ tax_col_1_label }}</th>
            <th style="width: {{ col_sgst }}%; border-right: 1px solid #000; padding: 3px 1px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">{{ tax_col_2_label }}</th>
                {% endif %}
            {% endif %}
            <th style="width: {{ col_amount }}%; padding: 3px 2px; text-align: center; font-size: 7px; font-weight: bold; vertical-align: middle;">Amount</th>
        </tr>
    </thead>
    <tbody>
        {% for row in rows %}
        <tr>
            <td style="border: 1px solid #000; padding: 2px 1px; text-align: center; font-size: 7px;">{{ row.sr }}</td>
            <td style="border: 1px solid #000; padding: 2px 2px; text-align: left; font-size: 7px; word-wrap: break-word; overflow-wrap: break-word;">{{ row.description }}</td>
            <td style="border: 1px solid #000; padding: 2px 1px; text-align: center; font-size: 7px;">{{ row.base_unit }}</td>
            <td style="border: 1px solid #000; padding: 2px 1px; text-align: center; font-size: 7px;">{{ row.packing_unit }}</td>
            {% if show_batch_columns %}
            <td style="border: 1px solid #000; padding: 2px 1px; text-align: center; font-size: 7px;">{{ row.batch_no }}</td>
            <td style="border: 1px solid #000; padding: 2px 1px; text-align: center; font-size: 7px;">{{ row.mfg_date }}</td>
            <td style="border: 1px solid #000; padding: 2px 1px; text-align: center; font-size: 7px;">{{ row.exp_date }}</td>
            {% endif %}
            <td style="border: 1px solid #000; padding: 2px 1px; text-align: center; font-size: 7px;">{{ row.hsn }}</td>
            <td style="border: 1px solid #000; padding: 2px 1px; text-align: center; font-size: 7px;">{{ row.qty }}</td>
            <td style="border: 1px solid #000; padding: 2px 1px; text-align: center; font-size: 7px; color: #d97706;">{{ row.free }}</td>
            <td style="border: 1px solid #000; padding: 2px 2px; text-align: right; font-size: 7px;">{{ row.rate }}</td>
            <td style="border: 1px solid #000; padding: 2px 1px; text-align: center; font-size: 7px;">{{ row.disc }}</td>
            {% if not export_invoice %}
                {% if show_igst %}
            <td style="border: 1px solid #000; padding: 2px 1px; text-align: center; font-size: 7px;">{{ row.igst_pct }}</td>
                {% else %}
            <td style="border: 1px solid #000; padding: 2px 1px; text-align: center; font-size: 7px;">{{ row.cgst_pct }}</td>
            <td style="border: 1px solid #000; padding: 2px 1px; text-align: center; font-size: 7px;">{{ row.sgst_pct }}</td>
                {% endif %}
            {% endif %}
            <td style="border: 1px solid #000; padding: 2px 2px; text-align: right; font-size: 7px; font-weight: bold;">{{ row.amount }}</td>
        </tr>
        {% endfor %}
        <!-- Spacer row -->
        <tr style="height: {% if rows|length < items_per_page %}120px{% else %}12px{% endif %};">
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            {% if show_batch_columns %}
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            {% endif %}
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            {% if not export_invoice %}
                {% if show_igst %}
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
                {% else %}
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
                {% endif %}
            {% endif %}
            <td style="border-left: 1px solid #000; border-right: 1px solid #000; border-top: 1px solid #000;"></td>
        </tr>
    </tbody>
</table>
{% endif %}

<!-- FOOTER -->
{% if is_last_page %}
<table style="width: 100%; border-left: 1px solid #000; border-right: 1px solid #000; border-bottom: 1px solid #000;">
    <tr>
        <td style="width: 60%; border-right: 1px solid #000; padding: 6px 8px; vertical-align: top;">
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
        <td style="width: 40%; padding: 0; vertical-align: top;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 3px 6px; font-size: 9.5px; border-bottom: 1px solid #000;">Sub Total</td>
                    <td style="padding: 3px 6px; font-size: 9.5px; text-align: right; border-bottom: 1px solid #000;">{{ subtotal }}</td>
                </tr>
                {% if not export_invoice %}
                    {% if show_igst %}
                <tr>
                    <td style="padding: 3px 6px; font-size: 9.5px; border-bottom: 1px solid #000;">{{ igst_label }}</td>
                    <td style="padding: 3px 6px; font-size: 9.5px; text-align: right; border-bottom: 1px solid #000;">{{ igst_total }}</td>
                </tr>
                    {% else %}
                <tr>
                    <td style="padding: 3px 6px; font-size: 9.5px; border-bottom: 1px solid #000;">{{ cgst_label }}</td>
                    <td style="padding: 3px 6px; font-size: 9.5px; text-align: right; border-bottom: 1px solid #000;">{{ cgst_total }}</td>
                </tr>
                <tr>
                    <td style="padding: 3px 6px; font-size: 9.5px; border-bottom: 1px solid #000;">{{ tax_secondary_label }}</td>
                    <td style="padding: 3px 6px; font-size: 9.5px; text-align: right; border-bottom: 1px solid #000;">{{ tax_secondary_total }}</td>
                </tr>
                    {% endif %}
                {% endif %}
                {% if round_off and round_off != '0.00' %}
                <tr>
                    <td style="padding: 3px 6px; font-size: 9.5px; border-bottom: 1px solid #000;">Round Off</td>
                    <td style="padding: 3px 6px; font-size: 9.5px; text-align: right; border-bottom: 1px solid #000;">{{ round_off }}</td>
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
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="height: 60px; text-align: center; vertical-align: bottom; border: none; padding-bottom: 5px;"></td>
                </tr>
                <tr>
                    <td style="text-align: center; border: none; padding: 2px 0 0 0; font-size: 8px; font-weight: 600; white-space: nowrap;">For {{ company_name }}</td>
                </tr>
                <tr>
                    <td style="text-align: center; border: none; padding: 2px 0 8px 0; font-size: 9px;">Authorized Signature</td>
                </tr>
            </table>
        </td>
    </tr>
</table>
{% else %}
<table style="width: 100%; border-left: 1px solid #000; border-right: 1px solid #000; border-bottom: 1px solid #000;">
    <tr>
        <td style="width: 100%; padding: 40px 8px 6px 8px; vertical-align: bottom; text-align: right; font-size: 9px; color: #666;">
            <em>Continued on next page...</em>
        </td>
    </tr>
</table>
{% endif %}

<div id="footer-content" style="text-align: center; font-size: 9px; color: #666; padding-top: 4px;">
    Page {{ current_page }} of {{ total_pages }}
</div>

</div>
</div>

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
        getattr(company, "country", ""),
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


def _format_order_currency_display(currency_code_or_label: str | None) -> str:
    """Format currency label once; avoid duplicates like 'JPY (¥) (JPY (¥))'."""
    raw = (currency_code_or_label or "").strip()
    if not raw:
        return "-"
    if "(" in raw and ")" in raw:
        return raw

    code = raw.upper()
    symbols = {"INR": "Rs.", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}
    symbol = symbols.get(code)
    if symbol:
        return f"{code} ({symbol})"
    return raw


def _format_currency_rupee(paise: int) -> str:
    """Format with Rs. symbol for grand total / balance due rows."""
    amount = (paise or 0) / 100
    return f"Rs.{amount:,.2f}"


def _format_total_with_currency(amount: float | int, currency_prefix: str) -> str:
    """Format total-section amounts as `<currency><space><amount>` for textual prefixes."""
    value = float(amount or 0)
    prefix = (currency_prefix or "").strip()
    if not prefix:
        return f"{value:,.2f}"
    no_space_prefixes = {"$", "€", "£", "¥"}
    separator = "" if prefix in no_space_prefixes else " "
    return f"{prefix}{separator}{value:,.2f}"


def _invoice_type_label(invoice_type: str | None) -> str:
    mapping = {
        "export_invoice": "Export Invoice",
        "within_state": "Within State",
        "other_states": "Other States",
        "union_territory": "Union Territory",
    }
    return mapping.get((invoice_type or "").strip().lower(), "Within State")


def _invoice_doc_title(invoice_type: str | None) -> str:
    token = (invoice_type or "").strip().lower()
    if token == "export_invoice":
        return "EXPORT INVOICE"
    return "SALES INVOICE"


def _decimal_to_str(value: Decimal | float | int | None) -> str:
    if value is None:
        return "0"
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def _get_corrected_cgst(doc, should_be_igst: bool = False) -> float:
    """Get CGST total (in rupees), honoring target mode."""
    if should_be_igst:
        return 0.0
    cgst = int(doc.total_cgst or 0)
    sgst = int(doc.total_sgst or 0)
    igst = int(doc.total_igst or 0)
    # If tax was stored as IGST (legacy), split it equally
    if cgst == 0 and sgst == 0 and igst > 0:
        return round(igst / 2) / 100
    return cgst / 100


def _get_corrected_sgst(doc, should_be_igst: bool = False) -> float:
    """Get SGST/UTGST total (in rupees), honoring target mode."""
    if should_be_igst:
        return 0.0
    cgst = int(doc.total_cgst or 0)
    sgst = int(doc.total_sgst or 0)
    igst = int(doc.total_igst or 0)
    # If tax was stored as IGST (legacy), split it equally
    if cgst == 0 and sgst == 0 and igst > 0:
        return (igst - round(igst / 2)) / 100
    return sgst / 100


def _get_corrected_igst(doc, should_be_igst: bool = False) -> float:
    """Get IGST total (in rupees), with fallback for legacy split storage."""
    if not should_be_igst:
        return 0.0
    cgst = int(doc.total_cgst or 0)
    sgst = int(doc.total_sgst or 0)
    igst = int(doc.total_igst or 0)
    if igst > 0:
        return igst / 100
    return (cgst + sgst) / 100



def _safe_text(value: Any) -> str:
    return str(value).strip() if value is not None and str(value).strip() else "-"


def _optional_text(value: Any) -> str:
    return str(value).strip() if value is not None and str(value).strip() else ""


def _get_uom_abbr(db: Session, uom_id) -> str:
    """Look up UOM abbreviation from the database."""
    if not uom_id:
        return "-"
    uom = db.query(UnitOfMeasure).filter(UnitOfMeasure.id == uom_id).first()
    return uom.abbreviation if uom else "-"


def _get_packing_label(db: Session, product: Product | None) -> str:
    """Get packing/order unit label from product's alt_uom_id only."""
    if not product or not product.alt_uom_id:
        return "-"
    uom = db.query(UnitOfMeasure).filter(UnitOfMeasure.id == product.alt_uom_id).first()
    if not uom:
        return "-"
    return _safe_text(uom.abbreviation or uom.name)


def _get_base_unit_label(product: Product | None) -> str:
    """Get base unit from product base-unit field (SKU column in this project)."""
    if not product:
        return "-"
    return _safe_text(product.sku)


def _get_payment_terms_label(supplier: Supplier | None) -> str:
    """Build payment terms text from a party's payment_terms_days field."""
    if not supplier:
        return "-"
    days = getattr(supplier, "payment_terms_days", None)
    if days is None:
        return "-"
    return f"{int(days)} Days"


def _amount_in_words(paise: int, currency_code: str = "INR", numbering_system: str = "indian") -> str:
    ones = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen",
    ]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def words_under_thousand(n: int) -> str:
        if n == 0:
            return ""
        if n < 20:
            return ones[n]
        if n < 100:
            return tens[n // 10] + (" " + ones[n % 10] if n % 10 else "")
        return ones[n // 100] + " Hundred" + (" and " + words_under_thousand(n % 100) if n % 100 else "")

    def words_indian(n: int) -> str:
        if n < 1000:
            return words_under_thousand(n)
        if n < 100000:
            return words_indian(n // 1000) + " Thousand" + (" " + words_indian(n % 1000) if n % 1000 else "")
        if n < 10000000:
            return words_indian(n // 100000) + " Lakh" + (" " + words_indian(n % 100000) if n % 100000 else "")
        return words_indian(n // 10000000) + " Crore" + (" " + words_indian(n % 10000000) if n % 10000000 else "")

    def words_international(n: int) -> str:
        if n < 1000:
            return words_under_thousand(n)
        if n < 1000000:
            return words_international(n // 1000) + " Thousand" + (" " + words_international(n % 1000) if n % 1000 else "")
        if n < 1000000000:
            return words_international(n // 1000000) + " Million" + (" " + words_international(n % 1000000) if n % 1000000 else "")
        if n < 1000000000000:
            return words_international(n // 1000000000) + " Billion" + (" " + words_international(n % 1000000000) if n % 1000000000 else "")
        return words_international(n // 1000000000000) + " Trillion" + (" " + words_international(n % 1000000000000) if n % 1000000000000 else "")

    major_units = (paise or 0) // 100
    minor_units = (paise or 0) % 100

    currency_token = (currency_code or "INR").strip().upper()
    major_label_map = {
        "INR": "Indian Rupees",
        "USD": "US Dollars",
        "EUR": "Euros",
        "GBP": "British Pounds",
    }
    minor_label_map = {
        "INR": "Paise",
        "USD": "Cents",
        "EUR": "Cents",
        "GBP": "Pence",
    }
    major_label = major_label_map.get(currency_token, currency_token)
    minor_label = minor_label_map.get(currency_token, "Cents")
    numbering = (numbering_system or "indian").strip().lower()
    to_words = words_international if numbering == "international" else words_indian

    chunks = []
    if major_units:
        chunks.append(f"{major_label} {to_words(major_units)}")
    else:
        chunks.append(f"{major_label} Zero")
    if minor_units:
        chunks.append(f"and {to_words(minor_units)} {minor_label}")
    return " ".join(chunks) + " Only"


def _resolve_company_image_src(image_url: str | None) -> str | None:
    """Convert a company image path to a base64 data URI that xhtml2pdf can render."""
    from PIL import Image, ImageFile

    if not image_url:
        return None

    logo_url = str(image_url)

    local_path = None
    if logo_url.startswith("/static/"):
        local_path = ROOT_DIR / logo_url.lstrip("/")
    else:
        p = Path(logo_url)
        if p.exists():
            local_path = p

    if not local_path or not local_path.exists():
        return None

    # Normalize to a PNG data URI so xhtml2pdf/reportlab handles it reliably.
    try:
        raw = local_path.read_bytes()
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        with Image.open(io.BytesIO(raw)) as img:
            normalized = img.convert("RGBA") if img.mode in {"RGBA", "LA", "P"} else img.convert("RGB")
            out = io.BytesIO()
            normalized.save(out, format="PNG")
            data = base64.b64encode(out.getvalue()).decode("ascii")
        return f"data:image/png;base64,{data}"
    except Exception:
        # Invalid logo should not break document generation.
        return None


def _resolve_logo_src(company: Company | None) -> str | None:
    return _resolve_company_image_src(company.logo_url if company else None)


def _resolve_ambassador_logo_src(company: Company | None) -> str | None:
    return _resolve_company_image_src(getattr(company, "ambassador_logo_url", None) if company else None)


def _read_image_bytes_from_src(image_src: str | None) -> bytes | None:
    """Read image bytes from a data URI or local file path."""
    if not image_src:
        return None

    src = str(image_src).strip()
    if not src:
        return None

    if src.startswith("data:"):
        marker = ";base64,"
        if marker not in src:
            return None
        _, encoded = src.split(marker, 1)
        if not encoded:
            return None
        try:
            return base64.b64decode(encoded)
        except Exception:
            return None

    local_path = Path(src)
    if local_path.exists() and local_path.is_file():
        try:
            return local_path.read_bytes()
        except Exception:
            return None
    return None


def _build_ambassador_background_pdf(
    logo_bytes: bytes,
    page_width: float,
    page_height: float,
) -> bytes | None:
    """Create a one-page PDF with centered, subtle ambassador-logo background."""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    try:
        image_reader = ImageReader(io.BytesIO(logo_bytes))
        image_width, image_height = image_reader.getSize()
    except Exception:
        return None

    if not image_width or not image_height:
        return None

    target_width = min(
        AMBASSADOR_WATERMARK_MAX_WIDTH_PT,
        page_width * AMBASSADOR_WATERMARK_PAGE_WIDTH_RATIO,
    )
    target_height = target_width * (float(image_height) / float(image_width))

    max_height = page_height * 0.55
    if target_height > max_height:
        target_height = max_height
        target_width = target_height * (float(image_width) / float(image_height))

    x = (page_width - target_width) / 2
    y = (page_height - target_height) / 2

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))
    c.saveState()
    try:
        c.setFillAlpha(AMBASSADOR_WATERMARK_OPACITY)
        c.setStrokeAlpha(AMBASSADOR_WATERMARK_OPACITY)
    except Exception:
        # Some PDF backends may not expose alpha APIs; keep rendering without hard failure.
        pass
    c.drawImage(
        image_reader,
        x,
        y,
        width=target_width,
        height=target_height,
        preserveAspectRatio=True,
        mask="auto",
    )
    c.restoreState()
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def _render_pdf(context: dict[str, Any]) -> bytes:
    html = Template(context.get("template_type", INVOICE_TEMPLATE)).render(**context)
    from xhtml2pdf import pisa
    buffer = io.BytesIO()
    status = pisa.CreatePDF(src=html, dest=buffer, encoding="utf-8")
    if status.err:
        raise RuntimeError("PDF generation failed with xhtml2pdf.")
    buffer.seek(0)
    return buffer.read()


def _chunk_items(items: list, chunk_size: int = BILLING_PDF_ITEMS_PER_PAGE) -> list[list]:
    """Split items into chunks of specified size for pagination."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def _render_pdf_with_pagination(context: dict[str, Any], template: str, rows: list[dict],
                                items_per_page: int = BILLING_PDF_ITEMS_PER_PAGE) -> bytes:
    """Render PDF with proper pagination - max items_per_page items per page.

    Each page is rendered as its own standalone PDF, then all pages are merged
    using pypdf so that headers, footers and page numbers work correctly.
    """
    from xhtml2pdf import pisa
    from pypdf import PdfReader, PdfWriter

    chunks = _chunk_items(rows, items_per_page)
    total_pages = len(chunks) if chunks else 1

    if not chunks:
        chunks = [rows]

    writer = PdfWriter()
    ambassador_logo_bytes = _read_image_bytes_from_src(context.get("company_ambassador_logo"))
    background_cache: dict[tuple[float, float], bytes | None] = {}

    for page_idx, chunk in enumerate(chunks):
        page_num = page_idx + 1
        is_last_page = (page_num == total_pages)

        page_context = {
            **context,
            "rows": chunk,
            "items_per_page": items_per_page,
            "current_page": page_num,
            "total_pages": total_pages,
            "is_last_page": is_last_page,
        }

        page_html = Template(template).render(**page_context)
        buf = io.BytesIO()
        status = pisa.CreatePDF(src=page_html, dest=buf, encoding="utf-8")
        if status.err:
            raise RuntimeError(f"PDF generation failed on page {page_num}.")
        buf.seek(0)
        reader = PdfReader(buf)
        for p in reader.pages:
            output_page = p
            if ambassador_logo_bytes:
                page_width = float(p.mediabox.width)
                page_height = float(p.mediabox.height)
                page_key = (round(page_width, 3), round(page_height, 3))

                if page_key not in background_cache:
                    background_cache[page_key] = _build_ambassador_background_pdf(
                        ambassador_logo_bytes,
                        page_width,
                        page_height,
                    )

                background_pdf = background_cache.get(page_key)
                if background_pdf:
                    background_page = PdfReader(io.BytesIO(background_pdf)).pages[0]
                    background_page.merge_page(p)
                    output_page = background_page

            writer.add_page(output_page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output.read()


def _layout_mode(rows: list[dict[str, str]], total_in_words: str, notes: str) -> str:
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
    currency_symbols = {"INR": "Rs.", "USD": "$", "EUR": "€", "GBP": "£"}
    cs = currency_symbols.get(currency, currency)
    tax_mode = determine_tax_mode(db, "supplier", po.supplier_id)
    show_po_igst = bool(tax_mode["gst_applicable"] and tax_mode["is_igst"])
    show_po_utgst = bool(tax_mode["gst_applicable"] and (not show_po_igst) and tax_mode["use_utgst"])

    for idx, item in enumerate(items, start=1):
        product = db.query(Product).filter(Product.id == item.product_id).first()
        gst_rate = int(item.gst_rate or 0)

        # Use DB-stored values directly — match website exactly
        taxable_paise = int(item.taxable_amount or 0)
        cgst_paise = int(item.cgst_amount or 0)
        sgst_paise = int(item.sgst_amount or 0)
        igst_paise = int(item.igst_amount or 0)
        total_paise = int(item.total_amount or 0)

        # For non-IGST layouts, split legacy IGST totals for display consistency.
        if not show_po_igst and cgst_paise == 0 and sgst_paise == 0 and igst_paise > 0:
            cgst_paise = round(igst_paise / 2)
            sgst_paise = igst_paise - cgst_paise

        half_rate = gst_rate / 2
        if not tax_mode["gst_applicable"]:
            cgst_pct = "-"
            sgst_pct = "-"
            igst_pct = "-"
        elif show_po_igst:
            cgst_pct = "-"
            sgst_pct = "-"
            igst_pct = f"{gst_rate}%"
        else:
            cgst_pct = f"{half_rate:.1f}%"
            sgst_pct = f"{half_rate:.1f}%"
            igst_pct = "-"

        rate_val = f"{(int(item.unit_price or 0) / 100):,.2f}"
        mrp_val = f"{(int(product.mrp or item.unit_price or 0) / 100):,.2f}" if product else rate_val

        rows.append(
            {
                "sr": str(idx),
                "description": _safe_text((item.description or (product.name if product else ""))),
                "packing": _get_packing_label(db, product),
                "batch": "-",
                "mfg": "-",
                "exp": "-",
                "hsn": _safe_text(product.hsn_code if product else None),
                "qty": f"{float(item.quantity):.2f}",
                "uom": _get_base_unit_label(product),
                "free": _decimal_to_str(getattr(item, "free_quantity", 0)),
                "rate": rate_val,
                "mrp": mrp_val,
                "disc": f"{float(item.discount_percent or 0):.1f}%",
                "taxable_amt": f"{(taxable_paise / 100):,.2f}",
                "gst_pct": f"{gst_rate}%",
                "cgst_pct": cgst_pct,
                "cgst_amt": f"{(cgst_paise / 100):,.2f}",
                "sgst_pct": sgst_pct,
                "sgst_amt": f"{(sgst_paise / 100):,.2f}",
                "igst_pct": igst_pct,
                "amount": f"{(total_paise / 100):,.2f}",
            }
        )

    if not rows:
        rows.append(
            {
                "sr": "1", "description": "-", "packing": "-", "batch": "-", "mfg": "-", "exp": "-",
                "hsn": "-", "qty": "0.00", "uom": "-", "free": "0", "rate": "0.00", "mrp": "0.00",
                "disc": "0.0%", "taxable_amt": "0.00", "gst_pct": "0%",
                "cgst_pct": "-", "cgst_amt": "0.00", "sgst_pct": "-", "sgst_amt": "0.00", "igst_pct": "-", "amount": "0.00",
            }
        )

    notes_text = _safe_text(po.notes)
    watermark_text = "Approved" if (po.status or "").strip().lower() != "draft" else "Not Approved"

    supplier_address = _safe_text(
        ", ".join(
            [p.strip() for p in [
                supplier.address_line1 if supplier else None,
                supplier.address_line2 if supplier else None,
                supplier.city if supplier else None,
                supplier.state if supplier else None,
                supplier.pincode if supplier else None,
            ] if p and p.strip()]
        )
    )

    context = {
        "template_type": PO_TEMPLATE,
        "doc_title": "PURCHASE ORDER",
        "doc_number": _safe_text(po.po_number),
        "doc_date": _format_date(po.order_date),
        "expected_delivery_date": _format_date(po.expected_delivery_date) if po.expected_delivery_date else "-",
        "terms": _get_payment_terms_label(supplier),
        "order_currency": _format_order_currency_display(currency),
        "cs": cs,
        "company_logo": _resolve_logo_src(company),
        "company_ambassador_logo": _resolve_ambassador_logo_src(company),
        "company_name": _safe_text(company.name if company else None),
        "company_address": _build_company_address(company),
        "company_gstin": _safe_text(company.gstin if company else None),
        "company_contact": _safe_text(company.phone if company and company.phone else (company.email if company else None)),
        "party_gstin": _safe_text(supplier.gstin if supplier else None),
        "place_of_supply": _safe_text(
            (getattr(company, "state", None) if company else None)
            or (supplier.place_of_supply if supplier else None)
            or (supplier.state if supplier else None)
        ),
        "bill_to_state": _safe_text((supplier.place_of_supply if supplier else None) or (supplier.state if supplier else None)),
        "bill_to_name": _safe_text(supplier.company_name if supplier else None),
        "bill_to_address": supplier_address,
        "under_delivery_tolerance": f"{float(po.under_delivery_tolerance or 0):.2f}",
        "over_delivery_tolerance": f"{float(po.over_delivery_tolerance or 0):.2f}",
        "rows": rows,
        "subtotal": _format_total_with_currency(int(po.subtotal or 0) / 100, cs),
        "gst_applicable": bool(tax_mode["gst_applicable"]),
        "show_igst": show_po_igst,
        "cgst_column_label": "CGST",
        "tax_secondary_column_label": "UTGST" if show_po_utgst else "SGST",
        "cgst_label": "CGST",
        "cgst_total": _format_total_with_currency(_get_corrected_cgst(po), cs),
        "sgst_label": "UTGST" if show_po_utgst else "SGST",
        "sgst_total": _format_total_with_currency(_get_corrected_sgst(po), cs),
        "igst_label": "IGST",
        "igst_total": _format_total_with_currency(_get_corrected_igst(po, should_be_igst=show_po_igst), cs),
        "grand_total_rupee": _format_total_with_currency(int(po.total_amount or 0) / 100, cs),
        "total_in_words": _amount_in_words(int(po.total_amount or 0), currency),
        "notes": notes_text,
        "watermark_text": watermark_text,
    }
    return _render_pdf_with_pagination(context, PO_TEMPLATE, rows, items_per_page=BILLING_PDF_ITEMS_PER_PAGE)


def generate_invoice_pdf(db: Session, invoice_id: UUID) -> bytes:
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id).first()
    if not invoice:
        raise ValueError("Invoice not found")

    company = db.query(Company).first()
    bill_to_customer_id = getattr(invoice, "bill_to_customer_id", None) or invoice.customer_id
    ship_to_customer_id = getattr(invoice, "ship_to_customer_id", None) or invoice.customer_id

    bill_to_customer = (
        db.query(Customer).filter(Customer.id == bill_to_customer_id).first()
        if bill_to_customer_id
        else None
    )
    ship_to_customer = (
        db.query(Customer).filter(Customer.id == ship_to_customer_id).first()
        if ship_to_customer_id
        else None
    )
    customer = bill_to_customer or ship_to_customer
    sales_order = db.query(SalesOrder).filter(SalesOrder.id == invoice.sales_order_id).first() if invoice.sales_order_id else None
    items = (
        db.query(SalesInvoiceItem)
        .filter(SalesInvoiceItem.invoice_id == invoice.id, SalesInvoiceItem.is_deleted == False)
        .all()
    )

    rows: list[dict[str, str]] = []
    # Get currency from customer or sales order — never hardcode
    currency = "INR"
    if sales_order and hasattr(sales_order, "currency_code") and sales_order.currency_code:
        currency = sales_order.currency_code
    elif customer and hasattr(customer, "currency_code") and customer.currency_code:
        currency = customer.currency_code
    currency_symbols = {"INR": "Rs.", "USD": "$", "EUR": "€", "GBP": "£"}
    cs = currency_symbols.get(currency, currency)

    invoice_type_token = (getattr(invoice, "invoice_type", "") or "").strip().lower()
    if not invoice_type_token:
        derived_customer_id = ship_to_customer_id or bill_to_customer_id
        invoice_type_token = (
            determine_default_invoice_type(db, derived_customer_id)
            if derived_customer_id
            else "within_state"
        )
    invoice_type_label = _invoice_type_label(invoice_type_token)
    export_invoice = invoice_type_token == "export_invoice"
    show_igst = invoice_type_token == "other_states"
    show_utgst = invoice_type_token == "union_territory"
    watermark_text = "Approved" if (invoice.status or "").strip().lower() != "draft" else "Not Approved"

    for idx, item in enumerate(items, start=1):
        product = db.query(Product).filter(Product.id == item.product_id).first()
        gst_rate = int(item.gst_rate or 0)
        half_rate = gst_rate / 2

        # Use DB-stored values directly — match website exactly
        taxable_paise = int(item.taxable_amount or 0)
        cgst_paise = int(item.cgst_amount or 0)
        sgst_paise = int(item.sgst_amount or 0)
        igst_paise = int(item.igst_amount or 0)
        total_paise = int(item.total_amount or 0)

        # For non-IGST layouts, split any legacy IGST for display consistency.
        if not show_igst and cgst_paise == 0 and sgst_paise == 0 and igst_paise > 0:
            cgst_paise = round(igst_paise / 2)
            sgst_paise = igst_paise - cgst_paise

        rate_val = f"{(int(item.unit_price or 0) / 100):,.2f}"
        base_unit = _get_base_unit_label(product)
        packing_unit = _get_packing_label(db, product)
        batch_no = _safe_text(getattr(item, "batch_no", None))
        mfg_date = _format_date(getattr(item, "manufacture_date", None))
        exp_date = _format_date(getattr(item, "expiry_date", None))

        rows.append(
            {
                "sr": str(idx),
                "description": _safe_text((item.description or (product.name if product else ""))),
                "batch_no": batch_no,
                "mfg_date": mfg_date,
                "exp_date": exp_date,
                "hsn": _safe_text(product.hsn_code if product else None),
                "qty": f"{float(item.quantity):.2f}",
                "free": _decimal_to_str(getattr(item, "free_quantity", 0)),
                "base_unit": base_unit,
                "packing_unit": packing_unit,
                "rate": rate_val,
                "disc": f"{float(item.discount_percent or 0):.1f}%",
                "cgst_pct": f"{half_rate:.1f}%",
                "sgst_pct": f"{half_rate:.1f}%",
                "igst_pct": f"{gst_rate}%",
                "amount": f"{(total_paise / 100):,.2f}",
            }
        )

    if not rows:
        rows.append(
            {
                "sr": "1", "description": "-", "batch_no": "-", "mfg_date": "-", "exp_date": "-",
                "hsn": "-", "qty": "0.00", "free": "0", "base_unit": "-", "packing_unit": "-",
                "rate": "0.00", "disc": "0.0%", "cgst_pct": "0.0%", "sgst_pct": "0.0%", "igst_pct": "0%", "amount": "0.00",
            }
        )

    billing_parts = [
        bill_to_customer.billing_address_line1 if bill_to_customer else None,
        bill_to_customer.billing_address_line2 if bill_to_customer else None,
        bill_to_customer.billing_city if bill_to_customer else None,
        bill_to_customer.billing_state if bill_to_customer else None,
        bill_to_customer.billing_pincode if bill_to_customer else None,
        bill_to_customer.billing_country if bill_to_customer else None,
    ]
    shipping_parts = [
        ship_to_customer.shipping_address_line1 if ship_to_customer else None,
        ship_to_customer.shipping_address_line2 if ship_to_customer else None,
        ship_to_customer.shipping_city if ship_to_customer else None,
        ship_to_customer.shipping_state if ship_to_customer else None,
        ship_to_customer.shipping_pincode if ship_to_customer else None,
        ship_to_customer.shipping_country if ship_to_customer else None,
    ]
    ship_to_billing_parts = [
        ship_to_customer.billing_address_line1 if ship_to_customer else None,
        ship_to_customer.billing_address_line2 if ship_to_customer else None,
        ship_to_customer.billing_city if ship_to_customer else None,
        ship_to_customer.billing_state if ship_to_customer else None,
        ship_to_customer.billing_pincode if ship_to_customer else None,
        ship_to_customer.billing_country if ship_to_customer else None,
    ]

    ship_to_address = ", ".join([p.strip() for p in shipping_parts if p and p.strip()])
    if not ship_to_address:
        ship_to_address = ", ".join([p.strip() for p in ship_to_billing_parts if p and p.strip()])
    if not ship_to_address:
        ship_to_address = ", ".join([p.strip() for p in billing_parts if p and p.strip()])

    notes_text = _safe_text(invoice.notes if invoice.notes else (f"Sales Order: {sales_order.so_number}" if sales_order else "-"))
    invoice_country = None
    if ship_to_customer:
        invoice_country = ship_to_customer.shipping_country or ship_to_customer.billing_country
    if not invoice_country and bill_to_customer:
        invoice_country = bill_to_customer.shipping_country or bill_to_customer.billing_country
    amount_words_numbering = "indian"
    if export_invoice and invoice_country and not is_india_country(invoice_country):
        amount_words_numbering = "international"

    tax_col_1_label = "CGST"
    tax_col_2_label = "UTGST" if show_utgst else "SGST"
    tax_secondary_prefix = "UTGST" if show_utgst else "SGST"

    # GEN-001: Round-off computation (nearest 0/5 rule)
    exact_total_paise = int(invoice.total_taxable_amount or 0) + int(invoice.total_gst or 0)
    rounded_total_paise = round_paise_to_nearest_5(exact_total_paise)
    rounded_total_rupees = rounded_total_paise / 100
    round_off_value = (rounded_total_paise - exact_total_paise) / 100
    round_off_display = f"{round_off_value:+.2f}" if abs(round_off_value) >= 0.005 else "0.00"

    place_of_supply_value = (
        getattr(invoice, "supply_state", None)
        or (ship_to_customer.shipping_state if ship_to_customer else None)
        or (ship_to_customer.billing_state if ship_to_customer else None)
        or (bill_to_customer.billing_state if bill_to_customer else None)
    )

    context = {
        "doc_title": _invoice_doc_title(invoice_type_token),
        "export_invoice": export_invoice,
        "show_igst": show_igst,
        "tax_col_1_label": tax_col_1_label,
        "tax_col_2_label": tax_col_2_label,
        "unit_col_label": "Base Unit",
        "show_batch_columns": True,
        "doc_number_label": "Invoice Number",
        "doc_date_label": "Invoice Date",
        "doc_number": _safe_text(invoice.invoice_number),
        "doc_date": _format_date(invoice.invoice_date),
        "due_date": _format_date(invoice.due_date),
        "payment_terms": _get_payment_terms_label(customer),
        "order_currency": _format_order_currency_display(currency),
        "raw_currency": _safe_text(currency),
        "company_logo": _resolve_logo_src(company),
        "company_ambassador_logo": _resolve_ambassador_logo_src(company),
        "company_name": _safe_text(company.name if company else None),
        "company_address": _build_company_address(company),
        "company_gstin": _safe_text(company.gstin if company else None),
        "company_contact": _safe_text(company.phone if company and company.phone else (company.email if company else None)),
        "company_import_export_number": _optional_text(getattr(company, "import_export_number", None) if company else None),
        "account_holder_name": _optional_text(company.account_holder_name if company else None),
        "company_bank_name": _optional_text(company.bank_name if company else None),
        "company_bank_account_no": _optional_text(company.bank_account_no if company else None),
        "company_bank_ifsc": _optional_text(company.bank_ifsc if company else None),
        "company_bank_branch": _optional_text(company.bank_branch if company else None),
        "invoice_type_label": invoice_type_label,
        "import_export_code": _optional_text(getattr(invoice, "import_export_code", None)),
        "party_gstin": _safe_text(bill_to_customer.gstin if bill_to_customer else None),
        "bill_to_state": _safe_text(bill_to_customer.billing_state if bill_to_customer else None),
        "place_of_supply": _safe_text(place_of_supply_value),
        "bill_to_name": _safe_text(bill_to_customer.company_name if bill_to_customer else None),
        "bill_to_address": _safe_text(", ".join([p.strip() for p in billing_parts if p and p.strip()])),
        "bill_to_gstin": _safe_text(bill_to_customer.gstin if bill_to_customer else None),
        "ship_to_name": _safe_text(
            (ship_to_customer.company_name if ship_to_customer else None)
            or (bill_to_customer.company_name if bill_to_customer else None)
        ),
        "ship_to_address": _safe_text(ship_to_address),
        "ship_to_gstin": _safe_text(
            (ship_to_customer.gstin if ship_to_customer else None)
            or (bill_to_customer.gstin if bill_to_customer else None)
        ),
        "rows": rows,
        "subtotal": _format_total_with_currency(int(invoice.subtotal or 0) / 100, cs),
        "cgst_label": "CGST",
        "cgst_total": _format_total_with_currency(_get_corrected_cgst(invoice, should_be_igst=show_igst), cs),
        "tax_secondary_label": tax_secondary_prefix,
        "tax_secondary_total": _format_total_with_currency(_get_corrected_sgst(invoice, should_be_igst=show_igst), cs),
        "igst_label": "IGST",
        "igst_total": _format_total_with_currency(_get_corrected_igst(invoice, should_be_igst=show_igst), cs),
        "round_off": round_off_display,
        "grand_total_rupee": _format_total_with_currency(rounded_total_rupees, cs),
        "balance_due_rupee": _format_total_with_currency(int(invoice.amount_due or invoice.total_amount or 0) / 100, cs),
        "total_in_words": _amount_in_words(int(rounded_total_rupees * 100), currency, numbering_system=amount_words_numbering),
        "notes": notes_text,
        "watermark_text": watermark_text,
    }
    return _render_pdf_with_pagination(context, INVOICE_TEMPLATE, rows, items_per_page=BILLING_PDF_ITEMS_PER_PAGE)


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

    # Get currency from customer record — never hardcode
    currency = "INR"
    if customer and hasattr(customer, "currency_code") and customer.currency_code:
        currency = customer.currency_code
    currency_symbols = {"INR": "Rs.", "USD": "$", "EUR": "€", "GBP": "£"}
    cs = currency_symbols.get(currency, currency)

    rows: list[dict[str, str]] = []
    quotation_invoice_type = determine_default_invoice_type(db, quotation.customer_id) if customer else "within_state"
    export_invoice = quotation_invoice_type == "export_invoice"
    show_igst = quotation_invoice_type == "other_states"
    show_utgst = quotation_invoice_type == "union_territory"
    invoice_type_label = _invoice_type_label(quotation_invoice_type)
    tax_col_1_label = "CGST"
    tax_col_2_label = "UTGST" if show_utgst else "SGST"
    tax_secondary_label = "UTGST" if show_utgst else "SGST"

    for idx, item in enumerate(items, start=1):
        product = db.query(Product).filter(Product.id == item.product_id).first()
        gst_rate = int(item.gst_rate or 0)
        half_rate = gst_rate / 2

        # Use DB-stored values directly — match website exactly
        taxable_paise = int(item.taxable_amount or 0)
        cgst_paise = int(item.cgst_amount or 0)
        sgst_paise = int(item.sgst_amount or 0)
        igst_paise = int(item.igst_amount or 0)
        total_paise = int(item.total_amount or 0)

        # Always split as CGST+SGST — convert any legacy IGST data
        if cgst_paise == 0 and sgst_paise == 0 and igst_paise > 0:
            cgst_paise = round(igst_paise / 2)
            sgst_paise = igst_paise - cgst_paise

        rate_val = f"{(int(item.unit_price or 0) / 100):,.2f}"
        base_unit = _get_base_unit_label(product)
        packing_unit = _get_packing_label(db, product)
        free_quantity = getattr(item, "free_quantity", 0)

        rows.append(
            {
                "sr": str(idx),
                "description": _safe_text((item.description or (product.name if product else ""))),
                "hsn": _safe_text(product.hsn_code if product else None),
                "qty": f"{float(item.quantity):.2f}",
                "free": _decimal_to_str(free_quantity),
                "base_unit": base_unit,
                "packing_unit": packing_unit,
                "rate": rate_val,
                "disc": f"{float(item.discount_percent or 0):.1f}%",
                "cgst_pct": f"{half_rate:.1f}%",
                "sgst_pct": f"{half_rate:.1f}%",
                "igst_pct": f"{gst_rate}%",
                "amount": f"{(total_paise / 100):,.2f}",
            }
        )

    if not rows:
        rows.append(
            {
                "sr": "1", "description": "-",
                "hsn": "-", "qty": "0.00", "free": "0", "base_unit": "-", "packing_unit": "-",
                "rate": "0.00", "disc": "0.0%", "cgst_pct": "0.0%", "sgst_pct": "0.0%", "igst_pct": "0%", "amount": "0.00",
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

    place_of_supply_value = _safe_text(
        (customer.shipping_state if customer else None)
        or (customer.billing_state if customer else None)
    )

    valid_until_text = _format_date(quotation.valid_until)
    notes_text = _safe_text(quotation.notes)
    watermark_text = "Approved" if (quotation.status or "").strip().lower() != "draft" else "Not Approved"

    context = {
        "doc_title": "QUOTATION",
        "export_invoice": export_invoice,
        "show_igst": show_igst,
        "tax_col_1_label": tax_col_1_label,
        "tax_col_2_label": tax_col_2_label,
        "unit_col_label": "Base Unit",
        "show_batch_columns": False,
        "doc_number_label": "Quotation Number",
        "doc_date_label": "Quotation Date",
        "doc_number": _safe_text(quotation.quotation_number),
        "doc_date": _format_date(quotation.quotation_date),
        "due_date": valid_until_text,
        "payment_terms": _get_payment_terms_label(customer),
        "order_currency": _format_order_currency_display(currency),
        "raw_currency": _safe_text(currency),
        "invoice_type_label": invoice_type_label,
        "company_logo": _resolve_logo_src(company),
        "company_ambassador_logo": _resolve_ambassador_logo_src(company),
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
        "place_of_supply": place_of_supply_value,
        "bill_to_name": _safe_text(customer.company_name if customer else None),
        "bill_to_address": _safe_text(", ".join([p.strip() for p in billing_parts if p and p.strip()])),
        "bill_to_gstin": _safe_text(customer.gstin if customer else None),
        "ship_to_name": _safe_text(customer.company_name if customer else None),
        "ship_to_address": _safe_text(ship_to_address),
        "ship_to_gstin": _safe_text(customer.gstin if customer else None),
        "rows": rows,
        "subtotal": _format_total_with_currency(int(quotation.subtotal or 0) / 100, cs),
        "cgst_label": "CGST",
        "cgst_total": _format_total_with_currency(_get_corrected_cgst(quotation, should_be_igst=show_igst), cs),
        "tax_secondary_label": tax_secondary_label,
        "tax_secondary_total": _format_total_with_currency(_get_corrected_sgst(quotation, should_be_igst=show_igst), cs),
        "igst_label": "IGST",
        "igst_total": _format_total_with_currency(_get_corrected_igst(quotation, should_be_igst=show_igst), cs),
        "grand_total_rupee": _format_total_with_currency(int(quotation.total_amount or 0) / 100, cs),
        "balance_due_rupee": _format_total_with_currency(int(quotation.total_amount or 0) / 100, cs),
        "total_in_words": _amount_in_words(int(quotation.total_amount or 0), currency),
        "notes": notes_text,
        "watermark_text": watermark_text,
    }
    return _render_pdf_with_pagination(context, INVOICE_TEMPLATE, rows, items_per_page=BILLING_PDF_ITEMS_PER_PAGE)
