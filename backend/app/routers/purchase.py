"""Purchase workflow router (PO, GRN, Purchase Return)."""
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permissions
from app.models.user import User
from app.models.company import Company
from app.models.product import Product, StockLedger
from app.models.supplier import Supplier
from app.models.purchase import (
    PurchaseOrder,
    PurchaseOrderItem,
    GoodsReceiptNote,
    GRNItem,
    PurchaseReturn,
    PurchaseReturnItem,
)
from app.schemas.purchase import (
    PurchaseOrderCreateRequest,
    PurchaseOrderStatusRequest,
    GRNCreateRequest,
    PurchaseReturnCreateRequest,
    PurchaseReturnStatusRequest,
)

router = APIRouter(tags=["purchase"])


def _generate_number(db: Session, entity: str) -> str:
    company = db.query(Company).first()
    if not company:
        company = Company(name="My Company")
        db.add(company)
        db.flush()

    if entity == "po":
        prefix = company.po_prefix
        counter = company.po_counter
        company.po_counter = counter + 1
    elif entity == "grn":
        prefix = company.grn_prefix
        counter = company.grn_counter
        company.grn_counter = counter + 1
    else:
        prefix = "PR"
        counter = getattr(company, "invoice_counter", 1)
        company.invoice_counter = counter + 1

    return f"{prefix}-{str(counter).zfill(5)}"


def _split_tax(taxable_amount: int, gst_rate: int, is_igst: bool) -> tuple[int, int, int]:
    if is_igst:
        return 0, 0, round(taxable_amount * gst_rate / 100)
    cgst = round(taxable_amount * (gst_rate / 2) / 100)
    sgst = round(taxable_amount * (gst_rate / 2) / 100)
    return cgst, sgst, 0


def _calc_item(quantity: float, unit_price: int, discount_percent: float, gst_rate: int, is_igst: bool) -> dict:
    gross = round(unit_price * quantity)
    discount = round(gross * discount_percent / 100)
    taxable = gross - discount
    cgst, sgst, igst = _split_tax(taxable, gst_rate, is_igst)
    return {
        "gross": gross,
        "discount": discount,
        "taxable": taxable,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total": taxable + cgst + sgst + igst,
    }


@router.get("/api/v1/purchase-orders")
async def list_purchase_orders(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_orders_read")),
):
    query = db.query(PurchaseOrder).filter(PurchaseOrder.is_deleted == False)
    if status:
        query = query.filter(PurchaseOrder.status == status)
    total = query.count()
    rows = query.order_by(PurchaseOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": rows, "total": total, "page": page, "page_size": page_size, "has_more": (page * page_size) < total}


@router.post("/api/v1/purchase-orders")
async def create_purchase_order(
    payload: PurchaseOrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_orders_write")),
):
    supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=400, detail="Invalid supplier")

    po_number = _generate_number(db, "po")
    po = PurchaseOrder(
        po_number=po_number,
        supplier_id=payload.supplier_id,
        order_date=payload.order_date,
        expected_delivery_date=payload.expected_delivery_date,
        status=payload.status,
        notes=payload.notes,
        created_by=current_user.id,
    )
    db.add(po)
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        product = db.query(Product).filter(Product.id == item.product_id, Product.is_deleted == False).first()
        if not product:
            raise HTTPException(status_code=400, detail="Invalid product")
        calc = _calc_item(item.quantity, item.unit_price, item.discount_percent, item.gst_rate, is_igst=False)
        row = PurchaseOrderItem(
            purchase_order_id=po.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=item.gst_rate,
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        )
        db.add(row)
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

    po.subtotal = subtotal
    po.total_discount = total_discount
    po.total_taxable_amount = total_taxable
    po.total_cgst = total_cgst
    po.total_sgst = total_sgst
    po.total_igst = total_igst
    po.total_gst = total_cgst + total_sgst + total_igst
    po.total_amount = total_taxable + po.total_gst
    db.commit()
    db.refresh(po)
    return po


@router.get("/api/v1/purchase-orders/{po_id}")
async def get_purchase_order(
    po_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_orders_read")),
):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id, PurchaseOrder.is_deleted == False).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    items = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == po_id).all()
    return {"purchase_order": po, "items": items}


@router.put("/api/v1/purchase-orders/{po_id}")
async def update_purchase_order(
    po_id: UUID,
    payload: PurchaseOrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_orders_write")),
):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id, PurchaseOrder.is_deleted == False).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if po.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft purchase orders can be edited")

    supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=400, detail="Invalid supplier")

    po.supplier_id = payload.supplier_id
    po.order_date = payload.order_date
    po.expected_delivery_date = payload.expected_delivery_date
    po.notes = payload.notes

    db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == po_id).delete()
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        calc = _calc_item(item.quantity, item.unit_price, item.discount_percent, item.gst_rate, is_igst=False)
        db.add(PurchaseOrderItem(
            purchase_order_id=po.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=item.gst_rate,
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        ))
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

    po.subtotal = subtotal
    po.total_discount = total_discount
    po.total_taxable_amount = total_taxable
    po.total_cgst = total_cgst
    po.total_sgst = total_sgst
    po.total_igst = total_igst
    po.total_gst = total_cgst + total_sgst + total_igst
    po.total_amount = total_taxable + po.total_gst
    db.commit()
    db.refresh(po)
    return po


@router.patch("/api/v1/purchase-orders/{po_id}/status")
async def update_purchase_order_status(
    po_id: UUID,
    payload: PurchaseOrderStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_orders_write")),
):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id, PurchaseOrder.is_deleted == False).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    allowed = {
        "draft": {"sent", "cancelled"},
        "sent": {"cancelled", "partial", "received"},
        "partial": {"received"},
    }
    if payload.status not in allowed.get(po.status, set()):
        raise HTTPException(status_code=400, detail="Invalid status transition")

    if po.status == "draft" and payload.status == "sent":
        supplier = db.query(Supplier).filter(Supplier.id == po.supplier_id, Supplier.is_deleted == False).first()
        if not supplier:
            raise HTTPException(status_code=400, detail="Cannot send PO: supplier reference is invalid")

    po.status = payload.status
    db.commit()
    db.refresh(po)
    return po


@router.get("/api/v1/grn")
async def list_grn(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_read")),
):
    query = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.is_deleted == False)
    if status:
        query = query.filter(GoodsReceiptNote.status == status)
    total = query.count()
    rows = query.order_by(GoodsReceiptNote.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": rows, "total": total, "page": page, "page_size": page_size, "has_more": (page * page_size) < total}


@router.post("/api/v1/grn")
async def create_grn(
    payload: GRNCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_write")),
):
    supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=400, detail="Invalid supplier")

    if payload.purchase_order_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == payload.purchase_order_id, PurchaseOrder.is_deleted == False).first()
        if not po:
            raise HTTPException(status_code=400, detail="Invalid purchase order")
        if po.status not in {"sent", "partial"}:
            raise HTTPException(status_code=400, detail="GRN can be created only from sent or partial purchase orders")
        if po.supplier_id != payload.supplier_id:
            raise HTTPException(status_code=400, detail="Supplier does not match selected purchase order")

    grn_number = _generate_number(db, "grn")
    grn = GoodsReceiptNote(
        grn_number=grn_number,
        purchase_order_id=payload.purchase_order_id,
        supplier_id=payload.supplier_id,
        supplier_invoice_number=payload.supplier_invoice_number,
        supplier_invoice_date=payload.supplier_invoice_date,
        receipt_date=payload.receipt_date,
        status="draft",
        notes=payload.notes,
        created_by=current_user.id,
    )
    db.add(grn)
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        calc = _calc_item(item.quantity, item.unit_price, item.discount_percent, item.gst_rate, is_igst=False)
        db.add(GRNItem(
            grn_id=grn.id,
            product_id=item.product_id,
            purchase_order_item_id=item.purchase_order_item_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=item.gst_rate,
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        ))
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

    grn.subtotal = subtotal
    grn.total_discount = total_discount
    grn.total_taxable_amount = total_taxable
    grn.total_cgst = total_cgst
    grn.total_sgst = total_sgst
    grn.total_igst = total_igst
    grn.total_gst = total_cgst + total_sgst + total_igst
    grn.total_amount = total_taxable + grn.total_gst

    db.commit()
    db.refresh(grn)
    return grn


@router.get("/api/v1/grn/{grn_id}")
async def get_grn(
    grn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_read")),
):
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == grn_id, GoodsReceiptNote.is_deleted == False).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    items = db.query(GRNItem).filter(GRNItem.grn_id == grn_id).all()
    return {"grn": grn, "items": items}


@router.put("/api/v1/grn/{grn_id}")
async def update_grn(
    grn_id: UUID,
    payload: GRNCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_write")),
):
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == grn_id, GoodsReceiptNote.is_deleted == False).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    if grn.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft GRN can be edited")

    supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id, Supplier.is_deleted == False).first()
    if not supplier:
        raise HTTPException(status_code=400, detail="Invalid supplier")

    if payload.purchase_order_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == payload.purchase_order_id, PurchaseOrder.is_deleted == False).first()
        if not po:
            raise HTTPException(status_code=400, detail="Invalid purchase order")
        if po.status not in {"sent", "partial"}:
            raise HTTPException(status_code=400, detail="GRN can be created only from sent or partial purchase orders")
        if po.supplier_id != payload.supplier_id:
            raise HTTPException(status_code=400, detail="Supplier does not match selected purchase order")

    grn.purchase_order_id = payload.purchase_order_id
    grn.supplier_id = payload.supplier_id
    grn.supplier_invoice_number = payload.supplier_invoice_number
    grn.supplier_invoice_date = payload.supplier_invoice_date
    grn.receipt_date = payload.receipt_date
    grn.notes = payload.notes

    db.query(GRNItem).filter(GRNItem.grn_id == grn_id).delete()
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        calc = _calc_item(item.quantity, item.unit_price, item.discount_percent, item.gst_rate, is_igst=False)
        db.add(GRNItem(
            grn_id=grn.id,
            product_id=item.product_id,
            purchase_order_item_id=item.purchase_order_item_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=item.gst_rate,
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        ))
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

    grn.subtotal = subtotal
    grn.total_discount = total_discount
    grn.total_taxable_amount = total_taxable
    grn.total_cgst = total_cgst
    grn.total_sgst = total_sgst
    grn.total_igst = total_igst
    grn.total_gst = total_cgst + total_sgst + total_igst
    grn.total_amount = total_taxable + grn.total_gst

    db.commit()
    db.refresh(grn)
    return grn


@router.post("/api/v1/grn/{grn_id}/confirm")
async def confirm_grn(
    grn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_write")),
):
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == grn_id, GoodsReceiptNote.is_deleted == False).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    if grn.status != "draft":
        raise HTTPException(status_code=400, detail="GRN is not in draft status")

    grn.status = "confirmed"
    items = db.query(GRNItem).filter(GRNItem.grn_id == grn_id).all()
    for item in items:
        db.add(StockLedger(
            product_id=item.product_id,
            transaction_type="purchase",
            reference_type="grn",
            reference_id=grn.id,
            reference_number=grn.grn_number,
            quantity=item.quantity,
            rate=item.unit_price,
            transaction_date=grn.receipt_date,
            created_by=current_user.id,
        ))
        if item.purchase_order_item_id:
            po_item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == item.purchase_order_item_id).first()
            if po_item:
                po_item.received_quantity = float(po_item.received_quantity) + float(item.quantity)

    if grn.purchase_order_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == grn.purchase_order_id).first()
        if po:
            po_items = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == po.id).all()
            if po_items and all(float(i.received_quantity) >= float(i.quantity) for i in po_items):
                po.status = "received"
            else:
                po.status = "partial"

    db.commit()
    db.refresh(grn)
    return grn


@router.post("/api/v1/grn/{grn_id}/cancel")
async def cancel_grn(
    grn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("grn_write")),
):
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == grn_id, GoodsReceiptNote.is_deleted == False).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    if grn.status != "draft":
        raise HTTPException(status_code=400, detail="Confirmed GRN cannot be cancelled")
    grn.status = "cancelled"
    db.commit()
    db.refresh(grn)
    return grn


@router.get("/api/v1/purchase-returns")
async def list_purchase_returns(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_returns_read")),
):
    query = db.query(PurchaseReturn).filter(PurchaseReturn.is_deleted == False)
    total = query.count()
    rows = query.order_by(PurchaseReturn.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": rows, "total": total, "page": page, "page_size": page_size, "has_more": (page * page_size) < total}


@router.post("/api/v1/purchase-returns")
async def create_purchase_return(
    payload: PurchaseReturnCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_returns_write")),
):
    grn = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.id == payload.grn_id, GoodsReceiptNote.status == "confirmed", GoodsReceiptNote.is_deleted == False).first()
    if not grn:
        raise HTTPException(status_code=400, detail="Invalid confirmed GRN")

    ret = PurchaseReturn(
        return_number=f"PR-{str(db.query(PurchaseReturn).count() + 1).zfill(5)}",
        supplier_id=payload.supplier_id,
        grn_id=payload.grn_id,
        return_date=payload.return_date,
        reason=payload.reason,
        status="draft",
        created_by=current_user.id,
    )
    db.add(ret)
    db.flush()

    subtotal = total_gst = 0
    for item in payload.items:
        grn_item = db.query(GRNItem).filter(GRNItem.id == item.grn_item_id).first() if item.grn_item_id else None
        if grn_item and float(item.quantity) > float(grn_item.quantity):
            raise HTTPException(status_code=400, detail="Return quantity exceeds received quantity")

        taxable = round(item.unit_price * item.quantity)
        cgst, sgst, igst = _split_tax(taxable, item.gst_rate, is_igst=False)
        total = taxable + cgst + sgst + igst
        db.add(PurchaseReturnItem(
            purchase_return_id=ret.id,
            product_id=item.product_id,
            grn_item_id=item.grn_item_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            taxable_amount=taxable,
            gst_rate=item.gst_rate,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst,
            total_amount=total,
        ))
        subtotal += taxable
        total_gst += cgst + sgst + igst

    ret.subtotal = subtotal
    ret.total_gst = total_gst
    ret.total_amount = subtotal + total_gst

    db.commit()
    db.refresh(ret)
    return ret


@router.get("/api/v1/purchase-returns/{return_id}")
async def get_purchase_return(
    return_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_returns_read")),
):
    ret = db.query(PurchaseReturn).filter(PurchaseReturn.id == return_id, PurchaseReturn.is_deleted == False).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Purchase return not found")
    items = db.query(PurchaseReturnItem).filter(PurchaseReturnItem.purchase_return_id == return_id).all()
    return {"purchase_return": ret, "items": items}


@router.post("/api/v1/purchase-returns/{return_id}/confirm")
async def confirm_purchase_return(
    return_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_returns_write")),
):
    ret = db.query(PurchaseReturn).filter(PurchaseReturn.id == return_id, PurchaseReturn.is_deleted == False).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Purchase return not found")
    if ret.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft purchase return can be confirmed")

    items = db.query(PurchaseReturnItem).filter(PurchaseReturnItem.purchase_return_id == return_id).all()
    for item in items:
        db.add(StockLedger(
            product_id=item.product_id,
            transaction_type="purchase_return",
            reference_type="purchase_return",
            reference_id=ret.id,
            reference_number=ret.return_number,
            quantity=-float(item.quantity),
            rate=item.unit_price,
            transaction_date=ret.return_date,
            created_by=current_user.id,
        ))

    ret.status = "confirmed"
    db.commit()
    db.refresh(ret)
    return ret


@router.post("/api/v1/purchase-returns/{return_id}/cancel")
async def cancel_purchase_return(
    return_id: UUID,
    payload: PurchaseReturnStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("purchase_returns_write")),
):
    ret = db.query(PurchaseReturn).filter(PurchaseReturn.id == return_id, PurchaseReturn.is_deleted == False).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Purchase return not found")
    if ret.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft purchase return can be cancelled")
    ret.status = "cancelled"
    db.commit()
    db.refresh(ret)
    return ret
