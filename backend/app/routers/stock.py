"""Stock adjustment router.

Production-ready with fixes for:
- BUG-01: Materialized view refresh after adjustments
- BUG-27: reference_id included for audit trail
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permissions, require_role
from app.models.inventory_count import InventoryCount, InventoryCountItem
from app.models.purchase import GoodsReceiptNote, GRNItem, PurchaseReturn, PurchaseReturnItem
from app.models.product import Product, StockLedger
from app.models.sales import SalesInvoice, SalesInvoiceItem, SalesReturn, SalesReturnItem
from app.models.user import User
from app.schemas.product import StockAdjustmentRequest, StockLedgerResponse
from app.schemas.stock import (
    InventoryCountBatchOptionResponse,
    InventoryCountBatchOptionsResponse,
    InventoryCountCreateRequest,
    InventoryCountDifferenceItemResponse,
    InventoryCountDifferenceResponse,
    InventoryCountItemResponse,
    InventoryCountNumberSearchResponse,
    InventoryCountResponse,
)
from app.services.stock_service import refresh_materialized_view

router = APIRouter(prefix="/api/v1/stock", tags=["stock"])


def _generate_inventory_count_number(db: Session, count_date: date) -> str:
    month_token = count_date.strftime("%b").upper()
    prefix = f"INV-{month_token}-"

    existing_numbers = (
        db.query(InventoryCount.count_number)
        .filter(
            InventoryCount.is_deleted == False,
            InventoryCount.count_number.like(f"{prefix}%"),
        )
        .all()
    )

    max_seq = 0
    for row in existing_numbers:
        number = (row[0] or "").strip()
        parts = number.split("-")
        if len(parts) != 3:
            continue
        suffix = parts[-1]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))

    return f"{prefix}{(max_seq + 1):03d}"


def _build_product_batch_snapshot(db: Session, product_id: UUID) -> dict[str, dict[str, Any]]:
    """Build positive available batch map for a product from transactional data."""
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
            func.coalesce(func.sum(SalesInvoiceItem.quantity), 0).label("qty"),
        )
        .join(SalesInvoice, SalesInvoiceItem.invoice_id == SalesInvoice.id)
        .filter(
            SalesInvoiceItem.product_id == product_id,
            SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
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


def _collect_inventory_count_date_errors(
    manufacture_date: date | None,
    expiry_date: date | None,
) -> list[str]:
    """Validate Inventory Count date constraints using date-only comparisons."""
    today = datetime.now(timezone.utc).date()
    errors: list[str] = []

    if manufacture_date and manufacture_date >= today:
        errors.append("Manufacturing date must be earlier than the current date")

    if expiry_date and expiry_date <= today:
        errors.append("Expiry date must be later than the current date")

    if manufacture_date and expiry_date and expiry_date <= manufacture_date:
        errors.append("Expiry date must be later than manufacturing date")

    return errors


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


@router.get("/inventory-counts/next-number")
async def get_inventory_count_number_preview(
    count_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("stock_ledger_read")),
):
    target_date = count_date or date.today()
    count_number = _generate_inventory_count_number(db, target_date)
    return {
        "count_number": count_number,
        "count_date": target_date.isoformat(),
    }


@router.get("/inventory-counts/batch-options", response_model=InventoryCountBatchOptionsResponse)
async def get_inventory_count_batch_options(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("stock_ledger_read")),
):
    product = db.query(Product).filter(Product.id == product_id, Product.is_deleted == False).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    snapshot = _build_product_batch_snapshot(db, product_id)
    batch_items = [
        InventoryCountBatchOptionResponse(
            batch_no=batch_no,
            available_qty=meta.get("available_qty", 0),
            manufacture_date=meta.get("manufacture_date").isoformat() if meta.get("manufacture_date") else None,
            expiry_date=meta.get("expiry_date").isoformat() if meta.get("expiry_date") else None,
        )
        for batch_no, meta in snapshot.items()
    ]
    batch_items.sort(
        key=lambda row: (
            row.expiry_date is None,
            row.expiry_date or "",
            row.batch_no,
        )
    )

    return InventoryCountBatchOptionsResponse(
        product_id=str(product_id),
        items=batch_items,
    )


@router.post("/inventory-counts", response_model=InventoryCountResponse, status_code=status.HTTP_201_CREATED)
async def create_inventory_count(
    payload: InventoryCountCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("stock_ledger_write")),
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="At least one item is required")

    product_ids = [item.product_id for item in payload.items]
    existing_products = (
        db.query(Product.id)
        .filter(Product.id.in_(product_ids), Product.is_deleted == False)
        .all()
    )
    existing_product_ids = {str(row[0]) for row in existing_products}
    missing_products = [str(pid) for pid in product_ids if str(pid) not in existing_product_ids]
    if missing_products:
        raise HTTPException(status_code=400, detail=f"Invalid product ids: {', '.join(missing_products)}")

    count_number = _generate_inventory_count_number(db, payload.count_date)
    inventory_count = InventoryCount(
        count_number=count_number,
        count_date=payload.count_date,
        count_performed_by=payload.count_performed_by.strip(),
        status="confirmed",
        created_by=current_user.id,
    )
    db.add(inventory_count)
    db.flush()

    created_items: list[InventoryCountItemResponse] = []
    for idx, item in enumerate(payload.items, start=1):
        item_date_errors = _collect_inventory_count_date_errors(
            item.manufacture_date,
            item.expiry_date,
        )
        if item_date_errors:
            raise HTTPException(status_code=400, detail=f"Line item {idx}: {item_date_errors[0]}")

        normalized_batch_no = (item.batch_no or "").strip() or None

        row = InventoryCountItem(
            inventory_count_id=inventory_count.id,
            serial_number=item.serial_number,
            product_id=item.product_id,
            product_description=item.product_description,
            quantity=item.quantity,
            batch_no=normalized_batch_no,
            manufacture_date=item.manufacture_date,
            expiry_date=item.expiry_date,
        )
        db.add(row)

        created_items.append(
            InventoryCountItemResponse(
                serial_number=item.serial_number,
                product_id=str(item.product_id),
                product_description=item.product_description,
                quantity=float(item.quantity),
                batch_no=normalized_batch_no,
                manufacture_date=item.manufacture_date.isoformat() if item.manufacture_date else None,
                expiry_date=item.expiry_date.isoformat() if item.expiry_date else None,
            )
        )

    db.commit()
    db.refresh(inventory_count)

    return InventoryCountResponse(
        id=str(inventory_count.id),
        count_number=inventory_count.count_number,
        count_date=inventory_count.count_date.isoformat(),
        count_performed_by=inventory_count.count_performed_by,
        status=inventory_count.status,
        items=created_items,
    )


@router.get("/inventory-counts/search", response_model=InventoryCountNumberSearchResponse)
async def search_inventory_count_numbers(
    q: str = Query(default="", max_length=60),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    token = (q or "").strip()

    query = db.query(InventoryCount.count_number).filter(InventoryCount.is_deleted == False)
    if token:
        query = query.filter(InventoryCount.count_number.ilike(f"%{token}%"))

    rows = (
        query.order_by(InventoryCount.count_date.desc(), InventoryCount.created_at.desc())
        .limit(limit)
        .all()
    )

    return InventoryCountNumberSearchResponse(items=[row[0] for row in rows if row[0]])


@router.get("/inventory-counts/differences", response_model=list[InventoryCountDifferenceResponse])
async def list_inventory_count_differences(
    limit: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    inventory_counts = (
        db.query(InventoryCount)
        .filter(
            InventoryCount.is_deleted == False,
            InventoryCount.status == "confirmed",
        )
        .order_by(InventoryCount.count_date.desc(), InventoryCount.created_at.desc())
        .limit(limit)
        .all()
    )
    if not inventory_counts:
        return []

    count_ids = [row.id for row in inventory_counts]
    count_items = (
        db.query(InventoryCountItem)
        .filter(
            InventoryCountItem.inventory_count_id.in_(count_ids),
            InventoryCountItem.is_deleted == False,
        )
        .order_by(InventoryCountItem.inventory_count_id.desc(), InventoryCountItem.serial_number.asc())
        .all()
    )

    items_by_count: dict[str, list[InventoryCountItem]] = {}
    product_ids = set()
    for row in count_items:
        key = str(row.inventory_count_id)
        items_by_count.setdefault(key, []).append(row)
        product_ids.add(row.product_id)

    product_rows = (
        db.query(Product.id, Product.product_code, Product.name)
        .filter(Product.id.in_(list(product_ids)), Product.is_deleted == False)
        .all()
    ) if product_ids else []
    product_meta = {
        str(row.id): {
            "product_code": row.product_code,
            "product_name": row.name,
        }
        for row in product_rows
    }

    existing_stock_rows = (
        db.query(
            StockLedger.product_id,
            func.coalesce(func.sum(StockLedger.quantity), 0).label("qty"),
        )
        .filter(
            StockLedger.product_id.in_(list(product_ids)),
            StockLedger.is_deleted == False,
        )
        .group_by(StockLedger.product_id)
        .all()
    ) if product_ids else []
    existing_stock_map = {str(row.product_id): float(row.qty or 0) for row in existing_stock_rows}

    responses: list[InventoryCountDifferenceResponse] = []
    for count in inventory_counts:
        rows = items_by_count.get(str(count.id), [])
        items = []
        for row in rows:
            product_key = str(row.product_id)
            counted_qty = float(row.quantity)
            existing_qty = float(existing_stock_map.get(product_key, 0.0))
            meta = product_meta.get(product_key, {})
            items.append(
                InventoryCountDifferenceItemResponse(
                    serial_number=row.serial_number,
                    product_id=product_key,
                    product_code=meta.get("product_code"),
                    product_name=meta.get("product_name"),
                    product_description=row.product_description,
                    batch_no=row.batch_no,
                    manufacture_date=row.manufacture_date.isoformat() if row.manufacture_date else None,
                    expiry_date=row.expiry_date.isoformat() if row.expiry_date else None,
                    counted_quantity=counted_qty,
                    existing_stock=existing_qty,
                    difference=round(counted_qty - existing_qty, 4),
                )
            )

        responses.append(
            InventoryCountDifferenceResponse(
                count_number=count.count_number,
                count_date=count.count_date.isoformat(),
                count_performed_by=count.count_performed_by,
                total_items=len(items),
                items=items,
            )
        )

    return responses


@router.get("/inventory-counts/{count_number}/difference", response_model=InventoryCountDifferenceResponse)
async def get_inventory_count_difference(
    count_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    inventory_count = (
        db.query(InventoryCount)
        .filter(
            InventoryCount.count_number == count_number,
            InventoryCount.is_deleted == False,
        )
        .first()
    )
    if not inventory_count:
        raise HTTPException(status_code=404, detail="Inventory count not found")

    count_items = (
        db.query(InventoryCountItem)
        .filter(
            InventoryCountItem.inventory_count_id == inventory_count.id,
            InventoryCountItem.is_deleted == False,
        )
        .order_by(InventoryCountItem.serial_number.asc())
        .all()
    )

    product_ids = list({item.product_id for item in count_items})
    product_rows = (
        db.query(Product.id, Product.product_code, Product.name)
        .filter(Product.id.in_(product_ids), Product.is_deleted == False)
        .all()
    ) if product_ids else []
    product_meta = {
        str(row.id): {
            "product_code": row.product_code,
            "product_name": row.name,
        }
        for row in product_rows
    }

    existing_stock_rows = (
        db.query(
            StockLedger.product_id,
            func.coalesce(func.sum(StockLedger.quantity), 0).label("qty"),
        )
        .filter(
            StockLedger.product_id.in_(product_ids),
            StockLedger.is_deleted == False,
        )
        .group_by(StockLedger.product_id)
        .all()
    ) if product_ids else []
    existing_stock_map = {str(row.product_id): float(row.qty or 0) for row in existing_stock_rows}

    items = []
    for row in count_items:
        product_key = str(row.product_id)
        counted_qty = float(row.quantity)
        existing_qty = float(existing_stock_map.get(product_key, 0.0))
        meta = product_meta.get(product_key, {})
        items.append(
            InventoryCountDifferenceItemResponse(
                serial_number=row.serial_number,
                product_id=product_key,
                product_code=meta.get("product_code"),
                product_name=meta.get("product_name"),
                product_description=row.product_description,
                batch_no=row.batch_no,
                manufacture_date=row.manufacture_date.isoformat() if row.manufacture_date else None,
                expiry_date=row.expiry_date.isoformat() if row.expiry_date else None,
                counted_quantity=counted_qty,
                existing_stock=existing_qty,
                difference=round(counted_qty - existing_qty, 4),
            )
        )

    return InventoryCountDifferenceResponse(
        count_number=inventory_count.count_number,
        count_date=inventory_count.count_date.isoformat(),
        count_performed_by=inventory_count.count_performed_by,
        total_items=len(items),
        items=items,
    )
