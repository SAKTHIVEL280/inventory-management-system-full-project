"""Company profile router."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
import base64

from app.database import get_db
from app.dependencies import get_current_user, require_permissions
from app.models.company import Company
from app.models.user import User
from app.schemas.company import CompanyResponse, CompanyUpdate, CompanyLogoResponse, CompanyBrandingResponse

router = APIRouter(prefix="/api/v1/company", tags=["company"])

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"


def _resolve_logo_file_path(logo_url: str) -> Path | None:
    if not logo_url:
        return None
    if logo_url.startswith("/static/"):
        file_name = logo_url.split("/static/", 1)[1]
        candidate = STATIC_DIR / file_name
        return candidate if candidate.exists() else None
    candidate = Path(logo_url)
    if candidate.exists() and candidate.is_file():
        return candidate
    return None


def _build_logo_data_url(file_path: Path) -> str | None:
    try:
        suffix = file_path.suffix.lower()
        media_type = "image/png" if suffix == ".png" else "image/jpeg"
        data = base64.b64encode(file_path.read_bytes()).decode("ascii")
        return f"data:{media_type};base64,{data}"
    except Exception:
        return None


@router.get("/branding", response_model=CompanyBrandingResponse)
async def get_company_branding(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = db.query(Company).first()
    if not company:
        return CompanyBrandingResponse(name="Inventory Management", logo_url=None, logo_data_url=None)

    logo_url = "/api/v1/company/logo-file" if company.logo_url else None
    logo_data_url = None
    if company.logo_url:
        file_path = _resolve_logo_file_path(company.logo_url)
        if file_path:
            logo_data_url = _build_logo_data_url(file_path)

    return CompanyBrandingResponse(
        name=company.name or "Inventory Management",
        logo_url=logo_url,
        logo_data_url=logo_data_url,
    )


@router.get("/logo-file")
async def get_company_logo_file(
    db: Session = Depends(get_db),
):
    company = db.query(Company).first()
    if not company or not company.logo_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company logo not found")

    file_path = _resolve_logo_file_path(company.logo_url)
    if not file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Logo file not found")

    media_type = "image/png" if file_path.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(path=str(file_path), media_type=media_type)


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

    # Save to backend static directory using extension matching the uploaded MIME type.
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    file_name = "logo.png" if content_type == "image/png" else "logo.jpg"
    file_path = STATIC_DIR / file_name
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    logo_url = f"/static/{file_name}"

    company = db.query(Company).first()
    if not company:
        company = Company(name="My Company")
        db.add(company)
    company.logo_url = logo_url
    db.commit()

    return CompanyLogoResponse(logo_url=logo_url)
