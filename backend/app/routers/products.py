"""Product master router."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permissions
from app.models.product import Product, ProductCategory, StockLedger, UnitOfMeasure
from app.models.user import User
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
        opening_stock=product.opening_stock,
        is_active=product.is_active,
        current_stock=float(stock),
        low_stock=float(stock) <= float(product.minimum_stock),
    )


@router.get("", response_model=ProductsListResponse)
async def list_products(
    search: str | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("products_read")),
):
    query = db.query(Product).filter(Product.is_deleted == False)

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

    total = query.count()
    products = (
        query.order_by(Product.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [_to_product_with_stock(product, _current_stock(db, product.id)) for product in products]

    return ProductsListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
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

    primary_uom = db.query(UnitOfMeasure).filter(UnitOfMeasure.id == payload.uom_id, UnitOfMeasure.is_active == True).first()
    if not primary_uom:
        raise HTTPException(status_code=400, detail="Invalid uom_id")

    if payload.alt_uom_id:
        alternate_uom = db.query(UnitOfMeasure).filter(UnitOfMeasure.id == payload.alt_uom_id, UnitOfMeasure.is_active == True).first()
        if not alternate_uom:
            raise HTTPException(status_code=400, detail="Invalid alt_uom_id")

    if payload.sku:
        duplicate_sku = db.query(Product).filter(Product.sku == payload.sku, Product.is_deleted == False).first()
        if duplicate_sku:
            raise HTTPException(status_code=400, detail="SKU already exists")

    product = Product(
        **payload.model_dump(exclude={"product_code"}),
        product_code=payload.product_code or _generate_product_code(db),
        created_by=current_user.id,
    )
    db.add(product)
    db.flush()

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

    db.commit()
    db.refresh(product)
    return _to_product_with_stock(product, _current_stock(db, product.id))


@router.get("/categories", response_model=list[ProductCategoryResponse])
async def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("categories_read")),
):
    categories = (
        db.query(ProductCategory)
        .filter(ProductCategory.is_deleted == False)
        .order_by(ProductCategory.name.asc())
        .all()
    )
    return [ProductCategoryResponse.model_validate(category) for category in categories]


@router.post("/categories", response_model=ProductCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: ProductCategoryCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("categories_write")),
):
    existing = (
        db.query(ProductCategory)
        .filter(func.lower(ProductCategory.name) == payload.name.lower(), ProductCategory.is_deleted == False)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Category already exists")

    category = ProductCategory(
        name=payload.name,
        description=payload.description,
        created_by=current_user.id,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return ProductCategoryResponse.model_validate(category)


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

    category = (
        db.query(ProductCategory)
        .filter(ProductCategory.id == payload.category_id, ProductCategory.is_deleted == False)
        .first()
    )
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category_id")

    primary_uom = db.query(UnitOfMeasure).filter(UnitOfMeasure.id == payload.uom_id, UnitOfMeasure.is_active == True).first()
    if not primary_uom:
        raise HTTPException(status_code=400, detail="Invalid uom_id")

    if payload.alt_uom_id:
        alternate_uom = db.query(UnitOfMeasure).filter(UnitOfMeasure.id == payload.alt_uom_id, UnitOfMeasure.is_active == True).first()
        if not alternate_uom:
            raise HTTPException(status_code=400, detail="Invalid alt_uom_id")

    if payload.sku:
        duplicate_sku = (
            db.query(Product)
            .filter(Product.sku == payload.sku, Product.id != product_id, Product.is_deleted == False)
            .first()
        )
        if duplicate_sku:
            raise HTTPException(status_code=400, detail="SKU already exists")

    update_data = payload.model_dump(exclude={"product_code"})
    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
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
