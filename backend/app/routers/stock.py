"""Stock adjustment router.

Production-ready with fixes for:
- BUG-01: Materialized view refresh after adjustments
- BUG-27: reference_id included for audit trail
"""
from datetime import date
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permissions
from app.models.product import Product, StockLedger
from app.models.user import User
from app.schemas.product import StockAdjustmentRequest, StockLedgerResponse
from app.services.stock_service import refresh_materialized_view

router = APIRouter(prefix="/api/v1/stock", tags=["stock"])


@router.post("/adjust", response_model=StockLedgerResponse, status_code=status.HTTP_201_CREATED)
async def adjust_stock(
    payload: StockAdjustmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("stock_ledger_write")),
):
    """
    Manually adjust stock for a product.
    
    - Positive quantity = add stock
    - Negative quantity = remove/deduct stock
    """
    product = db.query(Product).filter(
        Product.id == payload.product_id,
        Product.is_deleted == False
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Validate quantity
    if payload.quantity == 0:
        raise HTTPException(status_code=400, detail="Quantity cannot be zero")
    
    # Check if negative adjustment would result in negative stock
    current_qty = (
        db.query(func.coalesce(func.sum(StockLedger.quantity), 0))
        .filter(StockLedger.product_id == payload.product_id)
        .scalar() or 0
    )
    
    new_qty = Decimal(str(current_qty)) + Decimal(str(payload.quantity))
    if new_qty < 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient stock. Current: {current_qty}, Attempting to remove: {abs(payload.quantity)}"
        )
    
    # Create stock ledger entry (BUG-27: include reference_id=None explicitly)
    ledger_entry = StockLedger(
        product_id=payload.product_id,
        transaction_type="adjustment",
        reference_type="manual",
        reference_id=None,
        reference_number=f"ADJ-{date.today().isoformat()}",
        quantity=payload.quantity,
        rate=0,  # No cost impact for manual adjustments
        transaction_date=date.today(),
        notes=payload.notes or "Manual stock adjustment",
        created_by=current_user.id,
    )
    
    db.add(ledger_entry)

    # BUG-01: Refresh materialized view after stock change
    refresh_materialized_view(db)

    db.commit()
    db.refresh(ledger_entry)
    
    return StockLedgerResponse(
        id=str(ledger_entry.id),
        product_id=str(ledger_entry.product_id),
        transaction_type=ledger_entry.transaction_type,
        reference_type=ledger_entry.reference_type,
        reference_number=ledger_entry.reference_number,
        quantity=float(ledger_entry.quantity),
        rate=ledger_entry.rate,
        transaction_date=ledger_entry.transaction_date.isoformat(),
        notes=ledger_entry.notes,
    )


@router.get("/ledger/{product_id}", response_model=list[StockLedgerResponse])
async def get_product_stock_ledger(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("stock_ledger_read")),
):
    """Get stock ledger transactions for a specific product."""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.is_deleted == False
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    ledger_entries = (
        db.query(StockLedger)
        .filter(
            StockLedger.product_id == product_id,
            StockLedger.is_deleted == False
        )
        .order_by(StockLedger.transaction_date.desc(), StockLedger.created_at.desc())
        .all()
    )
    
    return [
        StockLedgerResponse(
            id=str(entry.id),
            product_id=str(entry.product_id),
            transaction_type=entry.transaction_type,
            reference_type=entry.reference_type,
            reference_number=entry.reference_number,
            quantity=float(entry.quantity),
            rate=entry.rate,
            transaction_date=entry.transaction_date.isoformat(),
            notes=entry.notes,
        )
        for entry in ledger_entries
    ]
