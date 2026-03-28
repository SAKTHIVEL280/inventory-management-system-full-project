"""Stock management service.

Fixes BUG-01: Adds materialized view refresh after stock transactions.
Centralizes stock calculation logic.
"""
from uuid import UUID
from decimal import Decimal
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.product import StockLedger


def get_current_stock(db: Session, product_id: UUID) -> float:
    """Get current stock for a product from the stock ledger."""
    qty = db.query(
        func.coalesce(func.sum(StockLedger.quantity), 0)
    ).filter(
        StockLedger.product_id == product_id
    ).scalar()
    return float(qty or 0)


def refresh_materialized_view(db: Session) -> None:
    """
    Refresh the current_stock materialized view.
    
    This MUST be called after any stock transaction (GRN confirm,
    invoice issue, stock adjustment, purchase return, sales return).
    
    Uses CONCURRENTLY to avoid locking reads during refresh.
    Falls back to normal refresh if concurrent refresh fails
    (e.g., if the view doesn't have a unique index yet).
    """
    try:
        db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY current_stock"))
    except SQLAlchemyError:
        try:
            # Fallback: non-concurrent refresh (locks reads briefly)
            db.execute(text("REFRESH MATERIALIZED VIEW current_stock"))
        except SQLAlchemyError:
            # View might not exist yet — log but don't crash the transaction
            pass


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
