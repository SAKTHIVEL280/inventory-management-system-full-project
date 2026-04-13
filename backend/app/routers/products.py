"""Product master router."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import enforce_resource_ownership, require_permissions
from app.models.product import Product, ProductCategory, StockLedger, UnitOfMeasure
from app.models.user import User
from app.utils.input_validation import normalize_search_query
from app.schemas.product import (
    ProductCategoryCreateRequest,
    ProductCategoryResponse,
    ProductCreateRequest,
    ProductUpdateRequest,
    ProductWithStockResponse,
    ProductsListResponse,
    UnitOfMeasureResponse,
)

router = APIRouter(prefix="/api/v1/products", tags=["products"])


def _scope_to_owner(query, model_cls, current_user: User):
    if current_user.role in {"admin", "accounting"}:
        return query
    owner_col = getattr(model_cls, "created_by", None)
    if owner_col is None:
        return query
    return query.filter(or_(owner_col == current_user.id, owner_col.is_(None)))


def _to_integrity_http_error(exc: IntegrityError) -> HTTPException:
    message = str(getattr(exc, "orig", exc)).lower()
    if "products_product_code_key" in message or "key (product_code)" in message:
        return HTTPException(status_code=400, detail="Product code already exists. Please retry.")
    return HTTPException(status_code=400, detail="Unable to save product due to duplicate values.")


def _generate_product_code(db: Session) -> str:
    count = db.query(Product).count()
    return f"PRD-{str(count + 1).zfill(5)}"


def _current_stock(db: Session, product_id: UUID) -> Decimal:
    quantity = (
        db.query(func.coalesce(func.sum(StockLedger.quantity), 0))
        .filter(StockLedger.product_id == product_id)
        .scalar()
    )
    return Decimal(quantity or 0)


def _current_stock_map(db: Session, product_ids: list[UUID]) -> dict[UUID, Decimal]:
    if not product_ids:
        return {}

    rows = (
        db.query(
            StockLedger.product_id,
            func.coalesce(func.sum(StockLedger.quantity), 0).label("quantity"),
        )
        .filter(
            StockLedger.product_id.in_(product_ids),
            StockLedger.is_deleted == False,
        )
        .group_by(StockLedger.product_id)
        .all()
    )

    return {row.product_id: Decimal(row.quantity or 0) for row in rows}


def _to_product_with_stock(product: Product, stock: Decimal) -> ProductWithStockResponse:
    return ProductWithStockResponse(
        id=product.id,
        product_code=product.product_code,
        sku=product.sku,
        name=product.name,
        description=product.description,
        category_id=product.category_id,
        uom_id=product.uom_id,
        alt_uom_id=product.alt_uom_id,
        alt_uom_conversion=product.alt_uom_conversion,
        hsn_code=product.hsn_code,
        gst_rate=product.gst_rate,
        purchase_price=product.purchase_price,
        selling_price=product.selling_price,
        mrp=product.mrp,
        minimum_stock=product.minimum_stock,
        safety_stock=product.safety_stock,
        opening_stock=product.opening_stock,
        is_active=product.is_active,
        current_stock=float(stock),
        low_stock=float(stock) <= float(product.safety_stock),
        below_safety_stock=False,
    )


@router.get("", response_model=ProductsListResponse)
async def list_products(
    search: str | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    all_products: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("products_read")),
):
    search = normalize_search_query(search)
    query = db.query(Product).filter(Product.is_deleted == False)
    query = _scope_to_owner(query, Product, current_user)

    if search:
        like_text = f"%{search}%"
        query = query.filter(
            or_(
                Product.product_code.ilike(like_text),
                Product.name.ilike(like_text),
                Product.sku.ilike(like_text),
            )
        )

    if category_id:
        query = query.filter(Product.category_id == category_id)

    if is_active is not None:
        query = query.filter(Product.is_active == is_active)

    # If all_products is True, fetch all products sorted by name
    if all_products:
        products = query.order_by(Product.name.asc()).all()
        total = len(products)
    else:
        # Paginated response - sort by name ascending (A-Z) by default
        total = query.count()
        products = (
            query.order_by(Product.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

    stock_by_product = _current_stock_map(db, [product.id for product in products])
    items = [
        _to_product_with_stock(product, stock_by_product.get(product.id, Decimal(0)))
        for product in products
    ]

    return ProductsListResponse(
        items=items,
        total=total,
        page=page if not all_products else 1,
        page_size=page_size if not all_products else total,
        has_more=False if all_products else (page * page_size) < total,
    )


@router.post("", response_model=ProductWithStockResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("products_write")),
):
    category = (
        db.query(ProductCategory)
        .filter(ProductCategory.id == payload.category_id, ProductCategory.is_deleted == False)
        .first()
    )
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category_id")
    enforce_resource_ownership(category.created_by, current_user)

    primary_uom = None
    if payload.uom_id:
        primary_uom = db.query(UnitOfMeasure).filter(UnitOfMeasure.id == payload.uom_id, UnitOfMeasure.is_active == True).first()
    else:
        primary_uom = db.query(UnitOfMeasure).filter(UnitOfMeasure.is_active == True).order_by(UnitOfMeasure.name.asc()).first()
    if not primary_uom:
        raise HTTPException(status_code=400, detail="No active Unit of Measure available")

    if payload.alt_uom_id:
        alternate_uom = db.query(UnitOfMeasure).filter(UnitOfMeasure.id == payload.alt_uom_id, UnitOfMeasure.is_active == True).first()
        if not alternate_uom:
            raise HTTPException(status_code=400, detail="Invalid alt_uom_id")

    product = Product(
        **payload.model_dump(exclude={"product_code", "uom_id"}),
        uom_id=primary_uom.id,
        product_code=payload.product_code or _generate_product_code(db),
        created_by=current_user.id,
    )
    db.add(product)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _to_integrity_http_error(exc)

    if payload.opening_stock > 0:
        ledger_entry = StockLedger(
            product_id=product.id,
            transaction_type="opening",
            reference_type="opening",
            reference_number="OPENING-STOCK",
            quantity=payload.opening_stock,
            rate=payload.purchase_price,
            transaction_date=date.today(),
            notes="Opening stock",
            created_by=current_user.id,
        )
        db.add(ledger_entry)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _to_integrity_http_error(exc)
    db.refresh(product)
    return _to_product_with_stock(product, _current_stock(db, product.id))


@router.get("/categories", response_model=list[ProductCategoryResponse])
async def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("categories_read")),
):
    query = db.query(ProductCategory).filter(ProductCategory.is_deleted == False)
    query = _scope_to_owner(query, ProductCategory, current_user)
    categories = query.order_by(ProductCategory.name.asc()).all()
    return [ProductCategoryResponse.model_validate(category) for category in categories]


@router.post("/categories", response_model=ProductCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: ProductCategoryCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("categories_write")),
):
    existing = (
        db.query(ProductCategory)
        .filter(func.lower(ProductCategory.name) == payload.name.lower())
        .first()
    )
    if existing:
        enforce_resource_ownership(existing.created_by, current_user)
    if existing and not existing.is_deleted:
        raise HTTPException(status_code=400, detail="Category already exists")

    # A soft-deleted row with the same name still exists in DB with a unique key.
    # Revive that row instead of inserting a duplicate and causing IntegrityError.
    if existing and existing.is_deleted:
        existing.description = payload.description
        existing.is_deleted = False
        existing.deleted_at = None
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return ProductCategoryResponse.model_validate(existing)

    category = ProductCategory(
        name=payload.name,
        description=payload.description,
        created_by=current_user.id,
    )
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Category already exists")
    db.refresh(category)
    return ProductCategoryResponse.model_validate(category)





@router.post("/apply-category-action")
async def apply_category_action(
    action: str = Query(..., description="Action: 'update' or 'delete'"),
    category_id: UUID = Query(..., description="Category ID"),
    name: str = Query(None, description="New name (for update action)"),
    description: str = Query(None, description="New description (for update action)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("categories_write")),
):
    """Universal endpoint for category update and delete operations."""
    category = (
        db.query(ProductCategory)
        .filter(ProductCategory.id == category_id, ProductCategory.is_deleted == False)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    enforce_resource_ownership(category.created_by, current_user)

    if action.lower() == "update":
        if not name:
            raise HTTPException(status_code=400, detail="Name is required for update")
        
        # Check if another category with the same name already exists
        existing = (
            db.query(ProductCategory)
            .filter(
                func.lower(ProductCategory.name) == name.lower(),
                ProductCategory.id != category_id,
                ProductCategory.is_deleted == False,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Category name already exists")

        category.name = name
        category.description = description or category.description
        db.commit()
        db.refresh(category)
        return ProductCategoryResponse.model_validate(category)
    
    elif action.lower() == "delete":
        category.is_deleted = True
        db.commit()
        return {"message": "Category deleted successfully"}
    
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}. Use 'update' or 'delete'")


@router.get("/uom", response_model=list[UnitOfMeasureResponse])
async def list_uom(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("uom_read")),
):
    uoms = db.query(UnitOfMeasure).filter(UnitOfMeasure.is_active == True).order_by(UnitOfMeasure.name.asc()).all()
    return [UnitOfMeasureResponse.model_validate(uom) for uom in uoms]


@router.get("/{product_id}", response_model=ProductWithStockResponse)
async def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("products_read")),
):
    product = db.query(Product).filter(Product.id == product_id, Product.is_deleted == False).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    enforce_resource_ownership(product.created_by, current_user)
    return _to_product_with_stock(product, _current_stock(db, product.id))


@router.put("/{product_id}", response_model=ProductWithStockResponse)
async def update_product(
    product_id: UUID,
    payload: ProductUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("products_write")),
):
    product = db.query(Product).filter(Product.id == product_id, Product.is_deleted == False).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    enforce_resource_ownership(product.created_by, current_user)

    category = (
        db.query(ProductCategory)
        .filter(ProductCategory.id == payload.category_id, ProductCategory.is_deleted == False)
        .first()
    )
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category_id")
    enforce_resource_ownership(category.created_by, current_user)

    primary_uom = None
    if payload.uom_id:
        primary_uom = db.query(UnitOfMeasure).filter(UnitOfMeasure.id == payload.uom_id, UnitOfMeasure.is_active == True).first()
    else:
        primary_uom = db.query(UnitOfMeasure).filter(UnitOfMeasure.is_active == True).order_by(UnitOfMeasure.name.asc()).first()
    if not primary_uom:
        raise HTTPException(status_code=400, detail="No active Unit of Measure available")

    if payload.alt_uom_id:
        alternate_uom = db.query(UnitOfMeasure).filter(UnitOfMeasure.id == payload.alt_uom_id, UnitOfMeasure.is_active == True).first()
        if not alternate_uom:
            raise HTTPException(status_code=400, detail="Invalid alt_uom_id")

    update_data = payload.model_dump(exclude={"product_code", "uom_id"})
    update_data["uom_id"] = primary_uom.id
    for field, value in update_data.items():
        setattr(product, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _to_integrity_http_error(exc)
    db.refresh(product)
    return _to_product_with_stock(product, _current_stock(db, product.id))


@router.delete("/{product_id}")
async def delete_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("products_write")),
):
    product = db.query(Product).filter(Product.id == product_id, Product.is_deleted == False).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    enforce_resource_ownership(product.created_by, current_user)

    stock = _current_stock(db, product_id)
    if stock > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete product '{product.name}' with existing stock ({stock} units). Please adjust stock to zero before deleting.",
        )

    product.is_deleted = True
    product.deleted_at = datetime.utcnow()
    db.commit()
    return {"message": "Product deleted"}
