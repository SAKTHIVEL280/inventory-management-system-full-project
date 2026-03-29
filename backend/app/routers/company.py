"""Company profile router."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
import os

from app.database import get_db
from app.dependencies import get_current_user, require_permissions
from app.models.company import Company
from app.models.user import User
from app.schemas.company import CompanyResponse, CompanyUpdate, CompanyLogoResponse

router = APIRouter(prefix="/api/v1/company", tags=["company"])


@router.get("", response_model=CompanyResponse)
async def get_company(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("company_read", "company_write")),
):
    company = db.query(Company).first()
    if not company:
        company = Company(name="My Company")
        db.add(company)
        db.commit()
        db.refresh(company)
    return company


@router.put("", response_model=CompanyResponse)
async def update_company(
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("company_write")),
):
    company = db.query(Company).first()
    if not company:
        company = Company(name=payload.name)
        db.add(company)

    for field, value in payload.model_dump().items():
        setattr(company, field, value)

    db.commit()
    db.refresh(company)
    return company


@router.post("/logo", response_model=CompanyLogoResponse)
async def upload_company_logo(
    logo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("company_write")),
):
    content_type = logo.content_type or ""
    if content_type not in {"image/png", "image/jpeg", "image/jpg"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PNG/JPG files are allowed",
        )

    file_bytes = await logo.read()
    if len(file_bytes) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logo file size must be <= 2MB",
        )

    # Save to static directory
    os.makedirs("static", exist_ok=True)
    file_path = "static/logo.png"
    with open(file_path, "wb") as f:
        f.write(file_bytes)
        
    logo_url = "/static/logo.png"

    company = db.query(Company).first()
    if not company:
        company = Company(name="My Company")
        db.add(company)
    company.logo_url = logo_url
    db.commit()

    return CompanyLogoResponse(logo_url=logo_url)
