"""Main FastAPI application."""
import logging
import uuid
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.logging_setup import configure_logging
from app.middleware import (
    AuditTrailMiddleware,
    ApiVersionCompatibilityMiddleware,
    CSRFMiddleware,
    HTTPSRedirectMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.rate_limit import limiter
from app.routers import auth, company, users, customers, suppliers, products, purchase, sales, payments, reports, stock, archive, compliance
from fastapi.staticfiles import StaticFiles

configure_logging()
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BACKEND_DIR / "static"

# Create static directory if it doesn't exist
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title=" Mecandria ERP",
    description="Complete inventory management with GST-aware purchase, sales, and reporting",
    version="1.0.0",
)

# Mount static files for company logo and assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Register shared rate limiter instance.
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning("Rate limit exceeded on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


# Attach request context first.
app.add_middleware(RequestContextMiddleware)

# Keep /api/v2 backward-compatible by internally mapping to v1 handlers.
app.add_middleware(ApiVersionCompatibilityMiddleware)

# Enforce HTTPS in production while honoring reverse-proxy forwarding headers.
if settings.environment == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

# Security headers should be applied before CORS.
app.add_middleware(SecurityHeadersMiddleware)

# CSRF validation is enforced only for mutating requests using cookie auth.
if settings.csrf_enabled:
    app.add_middleware(
        CSRFMiddleware,
        cookie_name=settings.csrf_cookie_name,
        header_name=settings.csrf_header_name,
        exempt_paths=settings.csrf_exempt_paths,
    )

# Baseline audit trail for all mutating API requests.
app.add_middleware(AuditTrailMiddleware)

# CORS configuration - MUST BE ADDED FIRST
allowed_origins = [settings.frontend_url]
if settings.environment != "production":
    allowed_origins.extend([
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ])
allowed_origins = list(dict.fromkeys(allowed_origins))
# For development, we can also use allow_origin_regex or just "*" if we trust the environment
# app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", settings.csrf_header_name, "X-Request-ID"],
    expose_headers=["Content-Range", "X-API-Version", "X-API-Compatible-With", "X-Request-ID"],
    max_age=3600,
)

# Include routers
app.include_router(auth.router)
app.include_router(company.router)
app.include_router(users.router)
app.include_router(customers.router)
app.include_router(suppliers.router)
app.include_router(products.router)
app.include_router(purchase.router)
app.include_router(sales.router)
app.include_router(payments.router)
app.include_router(reports.router)
app.include_router(stock.router)
app.include_router(archive.router)
app.include_router(compliance.router)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    message = str(getattr(exc, "orig", exc))
    lower = message.lower()
    
    # Log the full error for debugging
    logger.error(f"IntegrityError on {request.method} {request.url.path}: {message}")

    if "unique" in lower or "duplicate key value" in lower:
        detail = "Duplicate value found. Please use a unique value."
        if "email" in lower:
            detail = "Email already exists. Please use a different email."
        elif "product_code" in lower:
            detail = "Product code already exists. Please try again."
        return JSONResponse(status_code=400, content={"detail": detail, "path": request.url.path})

    if "foreign key" in lower:
        return JSONResponse(
            status_code=400,
            content={"detail": "Referenced record does not exist or is in use.", "path": request.url.path},
        )

    return JSONResponse(
        status_code=400,
        content={"detail": "Database constraint violation", "path": request.url.path},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    error_id = str(uuid.uuid4())
    logger.exception("Unhandled server error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_id": error_id,
            "path": request.url.path,
        },
    )


from fastapi.openapi.utils import get_openapi

def custom_openapi():
    # Force fresh generation by not checking app.openapi_schema first
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Force page_size limit to 500 in all endpoints
    for path in openapi_schema["paths"].values():
        for method in path.values():
            if "parameters" in method:
                for param in method["parameters"]:
                    if param["name"] == "page_size" and "schema" in param:
                        param["schema"]["maximum"] = 500
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/versions")
async def api_versions():
    """Report available API versions and compatibility behavior."""
    return {
        "default": "v1",
        "supported": ["v1", "v2"],
        "v2_mode": "compatibility_alias_to_v1",
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": " Mecandria ERP API",
        "docs": "/docs",
        "version": "1.0.0",
    }
