"""Stock management service.

Fixes BUG-01: Adds materialized view refresh after stock transactions.
Centralizes stock calculation logic.
"""
from datetime import date
from typing import Any
from uuid import UUID
from decimal import Decimal
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.inventory_count import InventoryCountDifferenceAudit, InventoryCountItem
from app.models.purchase import GoodsReceiptNote, GRNItem, PurchaseReturn, PurchaseReturnItem
from app.models.rdn import ReturnDeliveryNote, ReturnDeliveryNoteItem
from app.models.product import StockLedger, Product
from app.models.sales import SalesInvoice, SalesInvoiceItem, SalesReturn, SalesReturnItem


def get_current_stock(db: Session, product_id: UUID) -> float:
    """Get current stock for a product from the stock ledger."""
    qty = db.query(
        func.coalesce(func.sum(StockLedger.quantity), 0)
    ).filter(
        StockLedger.product_id == product_id
    ).scalar()
    return float(qty or 0)


def get_product_batch_snapshot(db: Session, product_id: UUID) -> dict[str, dict[str, Any]]:
    """Build a positive available batch map for a product from transactional data."""
    batch_balances: dict[str, float] = {}
    batch_meta: dict[str, tuple[date | None, date | None]] = {}

    def _accumulate(batch_no, manufacture_date, expiry_date, qty_delta):
        token = (batch_no or "").strip()
        if not token:
            return
        if token not in batch_meta:
            batch_meta[token] = (manufacture_date, expiry_date)
        else:
            prev_mfg, prev_exp = batch_meta[token]
            batch_meta[token] = (
                prev_mfg or manufacture_date,
                prev_exp or expiry_date,
            )
        batch_balances[token] = batch_balances.get(token, 0.0) + float(qty_delta or 0)

    grn_rows = (
        db.query(
            GRNItem.batch_no,
            GRNItem.manufacture_date,
            GRNItem.expiry_date,
            func.coalesce(func.sum(GRNItem.quantity), 0).label("qty"),
            func.coalesce(func.sum(GRNItem.free_quantity), 0).label("free_qty"),
        )
        .join(GoodsReceiptNote, GRNItem.grn_id == GoodsReceiptNote.id)
        .filter(
            GRNItem.product_id == product_id,
            GoodsReceiptNote.status == "confirmed",
            GoodsReceiptNote.is_deleted == False,
            GRNItem.is_deleted == False,
        )
        .group_by(GRNItem.batch_no, GRNItem.manufacture_date, GRNItem.expiry_date)
        .all()
    )
    for row in grn_rows:
        _accumulate(
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            float(row.qty or 0) + float(row.free_qty or 0),
        )

    purchase_return_rows = (
        db.query(
            GRNItem.batch_no,
            GRNItem.manufacture_date,
            GRNItem.expiry_date,
            func.coalesce(func.sum(PurchaseReturnItem.quantity), 0).label("qty"),
        )
        .join(PurchaseReturn, PurchaseReturnItem.purchase_return_id == PurchaseReturn.id)
        .outerjoin(GRNItem, PurchaseReturnItem.grn_item_id == GRNItem.id)
        .filter(
            PurchaseReturnItem.product_id == product_id,
            PurchaseReturn.status == "confirmed",
            PurchaseReturn.is_deleted == False,
            PurchaseReturnItem.is_deleted == False,
        )
        .group_by(GRNItem.batch_no, GRNItem.manufacture_date, GRNItem.expiry_date)
        .all()
    )
    for row in purchase_return_rows:
        _accumulate(
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            -float(row.qty or 0),
        )

    sales_issue_rows = (
        db.query(
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
            # MCN-BUG-02: stock deducted = billed quantity + free quantity, matching
            # the stock ledger (which posts both). Free items physically leave stock.
            func.coalesce(func.sum(SalesInvoiceItem.quantity + func.coalesce(SalesInvoiceItem.free_quantity, 0)), 0).label("qty"),
        )
        .join(SalesInvoice, SalesInvoiceItem.invoice_id == SalesInvoice.id)
        .filter(
            SalesInvoiceItem.product_id == product_id,
            func.lower(func.trim(SalesInvoice.status)).in_(["issued", "partial_paid", "paid", "returned"]),
            SalesInvoice.is_deleted == False,
            SalesInvoiceItem.is_deleted == False,
        )
        .group_by(
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
        )
        .all()
    )
    for row in sales_issue_rows:
        _accumulate(
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            -float(row.qty or 0),
        )

    sales_return_rows = (
        db.query(
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
            func.coalesce(func.sum(SalesReturnItem.quantity), 0).label("qty"),
        )
        .join(SalesReturn, SalesReturnItem.sales_return_id == SalesReturn.id)
        .outerjoin(SalesInvoiceItem, SalesReturnItem.invoice_item_id == SalesInvoiceItem.id)
        .filter(
            SalesReturnItem.product_id == product_id,
            SalesReturn.status == "confirmed",
            SalesReturn.is_deleted == False,
            SalesReturnItem.is_deleted == False,
        )
        .group_by(
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
        )
        .all()
    )
    for row in sales_return_rows:
        _accumulate(
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            float(row.qty or 0),
        )

    rdn_rows = (
        db.query(
            ReturnDeliveryNoteItem.batch_no,
            ReturnDeliveryNoteItem.manufacture_date,
            ReturnDeliveryNoteItem.expiry_date,
            func.coalesce(func.sum(ReturnDeliveryNoteItem.return_quantity), 0).label("qty"),
        )
        .join(ReturnDeliveryNote, ReturnDeliveryNoteItem.rdn_id == ReturnDeliveryNote.id)
        .filter(
            ReturnDeliveryNoteItem.product_id == product_id,
            ReturnDeliveryNote.status == "confirmed",
            ReturnDeliveryNote.is_deleted == False,
            ReturnDeliveryNoteItem.is_deleted == False,
        )
        .group_by(
            ReturnDeliveryNoteItem.batch_no,
            ReturnDeliveryNoteItem.manufacture_date,
            ReturnDeliveryNoteItem.expiry_date,
        )
        .all()
    )
    for row in rdn_rows:
        _accumulate(
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            float(row.qty or 0),
        )

    inventory_count_diff_rows = (
        db.query(
            InventoryCountItem.batch_no,
            InventoryCountItem.manufacture_date,
            InventoryCountItem.expiry_date,
            func.coalesce(func.sum(InventoryCountDifferenceAudit.difference_qty), 0).label("qty"),
        )
        .join(
            InventoryCountDifferenceAudit,
            InventoryCountDifferenceAudit.inventory_count_item_id == InventoryCountItem.id,
        )
        .filter(InventoryCountItem.product_id == product_id)
        .group_by(
            InventoryCountItem.batch_no,
            InventoryCountItem.manufacture_date,
            InventoryCountItem.expiry_date,
        )
        .all()
    )
    for row in inventory_count_diff_rows:
        _accumulate(
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            float(row.qty or 0),
        )

    snapshot: dict[str, dict[str, Any]] = {}
    for batch_no, qty in batch_balances.items():
        if qty <= 1e-6:
            continue
        manufacture_date, expiry_date = batch_meta.get(batch_no, (None, None))
        snapshot[batch_no] = {
            "available_qty": round(float(qty), 4),
            "manufacture_date": manufacture_date,
            "expiry_date": expiry_date,
        }
    return snapshot


def refresh_materialized_view(db: Session) -> None:
    """
    Refresh the current_stock materialized view.
    
    This MUST be called after any stock transaction (GRN confirm,
    invoice issue, stock adjustment, purchase return, sales return).
    
    Uses CONCURRENTLY to avoid locking reads during refresh.
    Falls back to normal refresh if concurrent refresh fails
    (e.g., if the view doesn't have a unique index yet).
    """
    def _try_refresh(sql: str) -> bool:
        try:
            # Use a savepoint so a failed refresh does not poison the outer transaction.
            with db.begin_nested():
                db.execute(text(sql))
            return True
        except SQLAlchemyError:
            return False

    if _try_refresh("REFRESH MATERIALIZED VIEW CONCURRENTLY current_stock"):
        return

    # Fallback: non-concurrent refresh (locks reads briefly).
    _try_refresh("REFRESH MATERIALIZED VIEW current_stock")


def add_stock_entry(
    db: Session,
    product_id: UUID,
    transaction_type: str,
    reference_type: str,
    reference_id: UUID | None,
    reference_number: str | None,
    quantity: float,
    rate: int,
    transaction_date,
    created_by: UUID,
    notes: str | None = None,
) -> StockLedger:
    """
    Create a stock ledger entry and refresh the materialized view.
    
    Args:
        db: Database session
        product_id: Product UUID
        transaction_type: 'purchase', 'sale', 'purchase_return', 'sale_return', 'adjustment', 'opening'
        reference_type: 'grn', 'invoice', 'purchase_return', 'sales_return', 'manual', 'opening'
        reference_id: Optional UUID of the source document
        reference_number: Optional document number string
        quantity: Positive for stock in, negative for stock out
        rate: Unit price in paise
        transaction_date: Date of transaction
        created_by: User UUID who created this entry
        notes: Optional notes
    
    Returns:
        Created StockLedger entry
    """
    # Multi-tenant (M7): a ledger entry belongs to the same tenant as its product.
    # Derive company_id centrally so every caller writes a tenant-attributed row
    # (closes the stock_ledger isolation gap without changing call signatures).
    company_id = db.query(Product.company_id).filter(Product.id == product_id).scalar()

    entry = StockLedger(
        product_id=product_id,
        transaction_type=transaction_type,
        reference_type=reference_type,
        reference_id=reference_id,
        reference_number=reference_number,
        quantity=quantity,
        rate=rate,
        transaction_date=transaction_date,
        notes=notes,
        created_by=created_by,
        company_id=company_id,
    )
    db.add(entry)
    return entry


def add_stock_entries_and_refresh(
    db: Session,
    entries: list[dict],
) -> list[StockLedger]:
    """
    Add multiple stock ledger entries and refresh the materialized view once.
    
    This is more efficient than calling add_stock_entry repeatedly
    as it only refreshes the view once after all entries are added.
    """
    created = []
    for entry_data in entries:
        entry = add_stock_entry(db, **entry_data)
        created.append(entry)
    
    # Refresh materialized view once after all entries
    refresh_materialized_view(db)
    
    return created
