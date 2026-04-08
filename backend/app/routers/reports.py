"""Reports router."""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permissions
from app.models.user import User
from app.models.product import Product, StockLedger
from app.models.sales import SalesInvoice, SalesInvoiceItem, SalesOrder, SalesReturn, SalesReturnItem
from app.models.purchase import GoodsReceiptNote, GRNItem, PurchaseOrder, PurchaseReturn, PurchaseReturnItem
from app.models.customer import Customer
from app.models.supplier import Supplier

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _ensure_valid_date_range(from_date: date, to_date: date) -> None:
    """Validate report date range parameters."""
    if from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail="from_date must be less than or equal to to_date",
        )


@router.get("/dashboard")
async def dashboard_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("dashboard_read")),
):
    today = date.today()
    month_start = today.replace(day=1)
    receivable_statuses = ["issued", "partial_paid"]

    # Count totals
    total_products = db.query(func.count(Product.id)).filter(
        Product.is_deleted == False
    ).scalar() or 0

    total_customers = db.query(func.count(Customer.id)).filter(
        Customer.is_deleted == False,
        Customer.is_active == True
    ).scalar() or 0

    total_suppliers = db.query(func.count(Supplier.id)).filter(
        Supplier.is_deleted == False,
        Supplier.is_active == True
    ).scalar() or 0

    # Low stock count
    low_stock_count = 0
    safety_stock_count = 0
    products = db.query(Product).filter(Product.is_deleted == False).all()
    for product in products:
        qty_scalar = db.query(func.coalesce(func.sum(StockLedger.quantity), 0)).filter(StockLedger.product_id == product.id).scalar() or 0
        qty = float(qty_scalar)
        safety = float(product.safety_stock or 0)
        minimum = float(product.safety_stock or 0)
        
        if qty <= safety and qty > 0:
            safety_stock_count += 1
        if qty <= minimum:
            low_stock_count += 1

    # Pending purchase orders
    pending_po_count = db.query(func.count(PurchaseOrder.id)).filter(
        PurchaseOrder.status.in_(["pending", "approved", "partial_received"]),
        PurchaseOrder.is_deleted == False,
    ).scalar() or 0

    # Pending sales orders
    pending_so_count = db.query(func.count(SalesOrder.id)).filter(
        SalesOrder.status.in_(["draft", "confirmed", "partial"]),
        SalesOrder.is_deleted == False,
    ).scalar() or 0

    # Today sales
    today_sales = db.query(func.coalesce(func.sum(SalesInvoice.total_amount), 0)).filter(
        SalesInvoice.invoice_date == today,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
    ).scalar() or 0

    # Month sales
    month_sales = db.query(func.coalesce(func.sum(SalesInvoice.total_amount), 0)).filter(
        SalesInvoice.invoice_date >= month_start,
        SalesInvoice.invoice_date <= today,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
    ).scalar() or 0

    # Outstanding receivables
    outstanding_receivables = db.query(func.coalesce(func.sum(SalesInvoice.amount_due), 0)).filter(
        SalesInvoice.amount_due > 0,
        SalesInvoice.status.in_(receivable_statuses),
        SalesInvoice.is_deleted == False,
    ).scalar() or 0

    # Overdue invoices count
    overdue_invoices_count = db.query(func.count(SalesInvoice.id)).filter(
        SalesInvoice.due_date < today,
        SalesInvoice.status.in_(["issued", "partial_paid"]),
        SalesInvoice.is_deleted == False,
    ).scalar() or 0

    # Sales trend (last 7 days)
    sales_trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        amount = db.query(func.coalesce(func.sum(SalesInvoice.total_amount), 0)).filter(
            SalesInvoice.invoice_date == day,
            SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
            SalesInvoice.is_deleted == False,
        ).scalar() or 0
        sales_trend.append({"date": day.isoformat(), "amount": int(amount)})

    # Top products
    top_products_query = db.query(
        Product.name,
        func.coalesce(func.sum(SalesInvoiceItem.quantity), 0).label("quantity_sold"),
        func.coalesce(func.sum(SalesInvoiceItem.total_amount), 0).label("amount"),
    ).join(SalesInvoiceItem, SalesInvoiceItem.product_id == Product.id).join(
        SalesInvoice, SalesInvoice.id == SalesInvoiceItem.invoice_id
    ).filter(
        SalesInvoice.invoice_date >= month_start,
        SalesInvoice.invoice_date <= today,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
        Product.is_deleted == False,
    ).group_by(Product.id, Product.name).order_by(text("quantity_sold DESC")).limit(5).all()

    top_products = [
        {
            "product_name": row.name,
            "quantity_sold": float(row.quantity_sold),
            "amount": int(row.amount),
        }
        for row in top_products_query
    ]

    def _cash_in_flow_rows(start_date: date | None = None):
        query = db.query(
            Customer.id,
            Customer.company_name,
            func.coalesce(func.sum(SalesInvoice.amount_due), 0).label("receivables_amount"),
        ).join(
            SalesInvoice,
            SalesInvoice.customer_id == Customer.id,
        ).filter(
            SalesInvoice.status.in_(receivable_statuses),
            SalesInvoice.amount_due > 0,
            SalesInvoice.is_deleted == False,
            Customer.is_deleted == False,
        )

        if start_date is not None:
            query = query.filter(
                SalesInvoice.invoice_date >= start_date,
                SalesInvoice.invoice_date <= today,
            )

        return query.group_by(
            Customer.id,
            Customer.company_name,
        ).order_by(
            text("receivables_amount DESC")
        ).limit(12).all()

    def _build_cash_in_flow(start_date: date):
        # If no receivables fall inside the date window, show overall outstanding
        # customers so the graph doesn't appear empty while receivables exist.
        rows = _cash_in_flow_rows(start_date)
        if not rows:
            rows = _cash_in_flow_rows()

        return [
            {
                "customer_id": str(row.id),
                "customer_name": row.company_name,
                "receivables_amount": int(row.receivables_amount),
            }
            for row in rows
        ]

    cash_in_flow = {
        "daily": _build_cash_in_flow(today),
        "weekly": _build_cash_in_flow(today - timedelta(days=6)),
        "monthly": _build_cash_in_flow(month_start),
    }

    # Recent invoices with customer names
    recent_invoices_rows = db.query(
        SalesInvoice, 
        Customer.company_name
    ).join(
        Customer, SalesInvoice.customer_id == Customer.id
    ).filter(
        SalesInvoice.is_deleted == False
    ).order_by(
        SalesInvoice.created_at.desc()
    ).limit(5).all()
    
    recent_invoices = [
        {
            "invoice_number": invoice.invoice_number,
            "customer_name": company_name,
            "amount": invoice.total_amount,
            "status": invoice.status,
            "date": invoice.invoice_date.isoformat() if invoice.invoice_date else "",
        }
        for invoice, company_name in recent_invoices_rows
    ]

    # Outstanding payables
    outstanding_payables = db.query(func.coalesce(func.sum(GoodsReceiptNote.total_amount), 0)).filter(
        GoodsReceiptNote.status == "confirmed",
        GoodsReceiptNote.is_deleted == False,
    ).scalar() or 0

    return {
        "total_products": int(total_products),
        "total_customers": int(total_customers),
        "total_suppliers": int(total_suppliers),
        "low_stock_count": int(low_stock_count),
        "safety_stock_count": int(safety_stock_count),
        "pending_purchase_orders": int(pending_po_count),
        "pending_sales_orders": int(pending_so_count),
        "today_sales": int(today_sales),
        "month_sales": int(month_sales),
        "outstanding_receivables": int(outstanding_receivables),
        "outstanding_payables": int(outstanding_payables),
        "overdue_invoices_count": int(overdue_invoices_count),
        "sales_trend": sales_trend,
        "top_products": top_products,
        "cash_in_flow": cash_in_flow,
        "recent_invoices": recent_invoices,
    }


@router.get("/stock")
async def stock_report(
    low_stock_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("stock_ledger_read", "reports_read")),
):
    rows = []
    NO_BATCH_TOKEN = "__UNASSIGNED__"

    def _normalize_batch(batch_no: str | None) -> str:
        token = (batch_no or "").strip()
        return token if token else NO_BATCH_TOKEN

    # Product-level totals remain sourced from stock ledger for consistency with
    # all stock-affecting flows and manual adjustments.
    product_totals = {
        str(row.product_id): float(row.qty or 0)
        for row in (
            db.query(
                StockLedger.product_id,
                func.coalesce(func.sum(StockLedger.quantity), 0).label("qty"),
            )
            .group_by(StockLedger.product_id)
            .all()
        )
    }

    # Build batch-wise balance from transactional references.
    # Key by (product, batch) so date metadata differences do not split the same batch.
    batch_balances: dict[tuple[str, str], float] = {}
    batch_meta: dict[tuple[str, str], tuple[date | None, date | None]] = {}

    def _accumulate(
        product_id,
        batch_no,
        manufacture_date,
        expiry_date,
        qty_delta,
    ):
        if not product_id:
            return
        key = (str(product_id), _normalize_batch(batch_no))
        if key not in batch_meta:
            batch_meta[key] = (manufacture_date, expiry_date)
        else:
            prev_mfg, prev_exp = batch_meta[key]
            batch_meta[key] = (
                prev_mfg or manufacture_date,
                prev_exp or expiry_date,
            )
        batch_balances[key] = batch_balances.get(key, 0.0) + float(qty_delta or 0)

    grn_rows = (
        db.query(
            GRNItem.product_id,
            GRNItem.batch_no,
            GRNItem.manufacture_date,
            GRNItem.expiry_date,
            func.coalesce(func.sum(GRNItem.quantity), 0).label("qty"),
            func.coalesce(func.sum(GRNItem.free_quantity), 0).label("free_qty"),
        )
        .join(GoodsReceiptNote, GRNItem.grn_id == GoodsReceiptNote.id)
        .filter(
            GoodsReceiptNote.status == "confirmed",
            GoodsReceiptNote.is_deleted == False,
            GRNItem.is_deleted == False,
        )
        .group_by(
            GRNItem.product_id,
            GRNItem.batch_no,
            GRNItem.manufacture_date,
            GRNItem.expiry_date,
        )
        .all()
    )
    for row in grn_rows:
        _accumulate(
            row.product_id,
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            float(row.qty or 0) + float(row.free_qty or 0),
        )

    purchase_return_rows = (
        db.query(
            PurchaseReturnItem.product_id,
            GRNItem.batch_no,
            GRNItem.manufacture_date,
            GRNItem.expiry_date,
            func.coalesce(func.sum(PurchaseReturnItem.quantity), 0).label("qty"),
        )
        .join(PurchaseReturn, PurchaseReturnItem.purchase_return_id == PurchaseReturn.id)
        .outerjoin(GRNItem, PurchaseReturnItem.grn_item_id == GRNItem.id)
        .filter(
            PurchaseReturn.status == "confirmed",
            PurchaseReturn.is_deleted == False,
            PurchaseReturnItem.is_deleted == False,
        )
        .group_by(
            PurchaseReturnItem.product_id,
            GRNItem.batch_no,
            GRNItem.manufacture_date,
            GRNItem.expiry_date,
        )
        .all()
    )
    for row in purchase_return_rows:
        _accumulate(
            row.product_id,
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            -float(row.qty or 0),
        )

    sales_issue_rows = (
        db.query(
            SalesInvoiceItem.product_id,
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
            func.coalesce(func.sum(SalesInvoiceItem.quantity), 0).label("qty"),
        )
        .join(SalesInvoice, SalesInvoiceItem.invoice_id == SalesInvoice.id)
        .filter(
            SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
            SalesInvoice.is_deleted == False,
            SalesInvoiceItem.is_deleted == False,
        )
        .group_by(
            SalesInvoiceItem.product_id,
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
        )
        .all()
    )
    for row in sales_issue_rows:
        _accumulate(
            row.product_id,
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            -float(row.qty or 0),
        )

    sales_return_rows = (
        db.query(
            SalesReturnItem.product_id,
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
            func.coalesce(func.sum(SalesReturnItem.quantity), 0).label("qty"),
        )
        .join(SalesReturn, SalesReturnItem.sales_return_id == SalesReturn.id)
        .outerjoin(SalesInvoiceItem, SalesReturnItem.invoice_item_id == SalesInvoiceItem.id)
        .filter(
            SalesReturn.status == "confirmed",
            SalesReturn.is_deleted == False,
            SalesReturnItem.is_deleted == False,
        )
        .group_by(
            SalesReturnItem.product_id,
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
        )
        .all()
    )
    for row in sales_return_rows:
        _accumulate(
            row.product_id,
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            float(row.qty or 0),
        )

    balances_by_product: dict[str, list[tuple[str, date | None, date | None, float]]] = {}
    for (product_id, batch_no), qty in batch_balances.items():
        if abs(qty) < 1e-6:
            continue
        manufacture_date, expiry_date = batch_meta.get((product_id, batch_no), (None, None))
        balances_by_product.setdefault(product_id, []).append(
            (batch_no, manufacture_date, expiry_date, qty)
        )

    products = db.query(Product).filter(Product.is_deleted == False).all()
    for product in products:
        product_id = str(product.id)
        safety = float(product.safety_stock or 0)
        product_qty = float(product_totals.get(product_id, 0.0))

        # STO-003/004/005: Keep low-stock status product-based; only row expansion
        # changes from product-level to batch-level.
        status = "Low Stock" if product_qty <= safety else "In Stock"
        if low_stock_only and status != "Low Stock":
            continue

        product_batches = list(balances_by_product.get(product_id, []))
        allocated_qty = sum(float(entry[3]) for entry in product_batches)
        unassigned_qty = product_qty - allocated_qty

        # Add reconciliation row only for positive residual quantity.
        # Negative residuals are data mismatches and should not create confusing
        # negative rows in Stock Master.
        if unassigned_qty > 1e-6 or not product_batches:
            product_batches.append((NO_BATCH_TOKEN, None, None, unassigned_qty if product_batches else product_qty))

        product_batches.sort(key=lambda entry: (entry[0] == NO_BATCH_TOKEN, entry[0]))

        for batch_no, manufacture_date, expiry_date, batch_qty in product_batches:
            rows.append({
                "product_code": product.product_code,
                "product_name": product.name,
                "hsn": product.hsn_code,
                "batch_no": None if batch_no == NO_BATCH_TOKEN else batch_no,
                "manufacture_date": manufacture_date,
                "expiry_date": expiry_date,
                "closing_qty": float(batch_qty),
                "min_stock": float(safety),
                "safety_stock": float(safety),
                "status": status,
            })

    rows.sort(key=lambda row: (row["product_name"] or "", row["batch_no"] or "~"))
    return {"items": rows, "total": len(rows)}


@router.get("/sales")
async def sales_report(
    from_date: date,
    to_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_valid_date_range(from_date, to_date)
    rows = db.query(SalesInvoice).filter(
        SalesInvoice.invoice_date >= from_date,
        SalesInvoice.invoice_date <= to_date,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
    ).all()
    return {
        "count": len(rows),
        "total_amount": int(sum(row.total_amount for row in rows)),
        "items": [
            {
                "invoice_number": row.invoice_number,
                "invoice_date": row.invoice_date.isoformat() if row.invoice_date else None,
                "total_amount": row.total_amount,
                "amount_paid": row.amount_paid,
                "amount_due": row.amount_due,
                "status": row.status,
            }
            for row in rows
        ],
    }


@router.get("/purchase")
async def purchase_report(
    from_date: date,
    to_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_valid_date_range(from_date, to_date)
    rows = db.query(GoodsReceiptNote).filter(
        GoodsReceiptNote.receipt_date >= from_date,
        GoodsReceiptNote.receipt_date <= to_date,
        GoodsReceiptNote.status == "confirmed",
        GoodsReceiptNote.is_deleted == False,
    ).all()
    return {
        "count": len(rows),
        "total_amount": int(sum(row.total_amount for row in rows)),
        "items": [
            {
                "grn_number": row.grn_number,
                "receipt_date": row.receipt_date.isoformat() if row.receipt_date else None,
                "supplier_id": str(row.supplier_id),
                "total_amount": row.total_amount,
            }
            for row in rows
        ],
    }


@router.get("/outstanding-receivables")
async def outstanding_receivables(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    rows = db.query(SalesInvoice).filter(
        SalesInvoice.amount_due > 0,
        SalesInvoice.status.in_(["issued", "partial_paid"]),
        SalesInvoice.is_deleted == False,
    ).all()
    return {
        "total_outstanding": int(sum(row.amount_due for row in rows)),
        "items": [
            {
                "invoice_number": row.invoice_number,
                "invoice_date": row.invoice_date.isoformat() if row.invoice_date else None,
                "due_date": row.due_date.isoformat() if row.due_date else None,
                "balance_due": row.amount_due,
            }
            for row in rows
        ],
    }


@router.get("/outstanding-payables")
async def outstanding_payables(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    rows = db.query(GoodsReceiptNote).filter(
        GoodsReceiptNote.status == "confirmed",
        GoodsReceiptNote.is_deleted == False,
    ).all()
    return {
        "total_outstanding": int(sum(row.total_amount for row in rows)),
        "items": [
            {
                "grn_number": row.grn_number,
                "receipt_date": row.receipt_date.isoformat() if row.receipt_date else None,
                "balance_due": row.total_amount,
            }
            for row in rows
        ],
    }


@router.get("/gstr1")
async def gstr1_report(
    from_date: date,
    to_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_valid_date_range(from_date, to_date)
    rows = db.query(SalesInvoice).filter(
        SalesInvoice.invoice_date >= from_date,
        SalesInvoice.invoice_date <= to_date,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
    ).all()
    return {
        "summary": {
            "total_taxable": int(sum(row.total_taxable_amount for row in rows)),
            "total_cgst": int(sum(row.total_cgst for row in rows)),
            "total_sgst": int(sum(row.total_sgst for row in rows)),
            "total_igst": int(sum(row.total_igst for row in rows)),
        },
        "count": len(rows),
    }


@router.get("/gstr3b")
async def gstr3b_report(
    from_date: date,
    to_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_valid_date_range(from_date, to_date)
    sales_rows = db.query(SalesInvoice).filter(
        SalesInvoice.invoice_date >= from_date,
        SalesInvoice.invoice_date <= to_date,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
    ).all()
    purchase_rows = db.query(GoodsReceiptNote).filter(
        GoodsReceiptNote.receipt_date >= from_date,
        GoodsReceiptNote.receipt_date <= to_date,
        GoodsReceiptNote.status == "confirmed",
        GoodsReceiptNote.is_deleted == False,
    ).all()

    output_tax = sum(row.total_gst for row in sales_rows)
    input_tax = sum(row.total_gst for row in purchase_rows)

    return {
        "output_tax": int(output_tax),
        "itc": int(input_tax),
        "net_tax_payable": int(output_tax - input_tax),
    }


@router.get("/pl")
async def profit_and_loss_report(
    from_date: date,
    to_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_valid_date_range(from_date, to_date)
    sales_rows = db.query(SalesInvoice).filter(
        SalesInvoice.invoice_date >= from_date,
        SalesInvoice.invoice_date <= to_date,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
    ).all()
    purchase_rows = db.query(GoodsReceiptNote).filter(
        GoodsReceiptNote.receipt_date >= from_date,
        GoodsReceiptNote.receipt_date <= to_date,
        GoodsReceiptNote.status == "confirmed",
        GoodsReceiptNote.is_deleted == False,
    ).all()

    net_sales = int(sum(row.total_taxable_amount for row in sales_rows))
    purchases = int(sum(row.total_taxable_amount for row in purchase_rows))
    gross_profit = net_sales - purchases

    margin = 0
    if net_sales > 0:
        margin = round((gross_profit / net_sales) * 100, 2)

    return {
        "net_sales": net_sales,
        "purchases": purchases,
        "gross_profit": gross_profit,
        "gross_profit_margin_percent": margin,
        "net_profit": gross_profit,
    }
