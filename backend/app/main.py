"""Main FastAPI application."""
import logging
from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.logging_setup import configure_logging
from app.middleware import (
    AuditTrailMiddleware,
    ApiVersionCompatibilityMiddleware,
    CSRFMiddleware,
    HTTPSRedirectMiddleware,
    RequestContextMiddleware,
)
from app.middleware.request_context import correlation_id
from app import rate_limit as rate_limit_module
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

# Explicit slowapi wiring for application-wide and route-level limits.
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit_api])
rate_limit_module.limiter = limiter

from app.routers import auth, company, users, customers, suppliers, products, purchase, sales, payments, reports, stock, archive, compliance, rdn, customization_options, proforma, master_data, subscription, super_admin, service_invoice, plan_config


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline browser security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' https://fonts.googleapis.com; "
            "script-src 'self'; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "connect-src 'self' http://localhost:8001 http://127.0.0.1:8001; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "object-src 'none'",
        )

        if request.url.scheme == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

        return response

# Mount static files for company logo and assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Register shared rate limiter instance.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


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

# CORS configuration
allowed_origins = [origin for origin in settings.frontend_allowed_origins if origin and origin != "*"]
if not allowed_origins:
    raise RuntimeError("CORS allow_origins must use explicit trusted origins; wildcard '*' is not allowed")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", settings.csrf_header_name, "X-Request-ID", "X-Correlation-ID"],
    expose_headers=["Content-Range", "X-API-Version", "X-API-Compatible-With", "X-Request-ID", "X-Correlation-ID"],
    max_age=3600,
)

# Include routers.
#
# Multi-tenant gating:
#  * require_module(...) — tenant whose plan excludes a module gets 403 "upgrade".
#    These routers map 1:1 to a subscription module. require_module also loads the
#    tenant (get_current_company), so a Super Admin (no tenant) is 403'd here too.
#  * require_tenant — hard tenant-isolation boundary (M1, BRD §10). Applied to the
#    cross-cutting tenant routers that are NOT module-gated (auth excluded — it must
#    work pre-tenant for login). This blocks Super Admins from reading any single
#    tenant's data directly and guarantees a tenant context exists, closing the
#    latent `if company_id:` soft-filter leak (without a tenant those filters were
#    skipped and returned every tenant's rows merged).
# Platform routers (subscription/super_admin) carry their own guards. The legacy
# tenant is PLATINUM, so all plan gates pass today (no behaviour change for it).
from app.dependencies import require_module, require_tenant

app.include_router(auth.router)
app.include_router(company.router, dependencies=[Depends(require_tenant)])
app.include_router(users.router, dependencies=[Depends(require_tenant)])
app.include_router(customers.router, dependencies=[Depends(require_module("masters"))])
app.include_router(suppliers.router, dependencies=[Depends(require_module("masters"))])
app.include_router(products.router, dependencies=[Depends(require_module("masters"))])
app.include_router(purchase.router, dependencies=[Depends(require_module("purchase"))])
app.include_router(sales.router, dependencies=[Depends(require_module("sales"))])
app.include_router(proforma.router, dependencies=[Depends(require_module("sales"))])
app.include_router(payments.router, dependencies=[Depends(require_module("accounts"))])
app.include_router(reports.router, dependencies=[Depends(require_tenant)])
app.include_router(stock.router, dependencies=[Depends(require_module("inventory"))])
app.include_router(rdn.router, dependencies=[Depends(require_module("sales"))])
app.include_router(customization_options.router, dependencies=[Depends(require_tenant)])
app.include_router(master_data.router, dependencies=[Depends(require_module("masters"))])
app.include_router(archive.router, dependencies=[Depends(require_tenant)])
app.include_router(compliance.router, dependencies=[Depends(require_tenant)])
app.include_router(subscription.router)
app.include_router(super_admin.router)
app.include_router(plan_config.router)
app.include_router(service_invoice.router)


_VALIDATION_MSG_REWRITES = (
    ("Input should be", "must be"),
    ("Value error, ", ""),
    ("value is not a valid", "is not a valid"),
)


def _humanize_validation_location(loc: tuple) -> str:
    """Render a pydantic error location as a readable field reference.

    e.g. ("body", "items", 0, "quantity") -> "Items #1 → Quantity".
    """
    segments: list[str] = []
    for part in loc:
        if part in ("body", "query", "path"):
            continue
        if isinstance(part, int):
            # Attach the 1-based index to the previous segment ("Items #1").
            if segments:
                segments[-1] = f"{segments[-1]} #{part + 1}"
            else:
                segments.append(f"#{part + 1}")
        else:
            label = str(part).replace("_", " ").strip()
            segments.append(label[:1].upper() + label[1:] if label else label)
    return " → ".join(s for s in segments if s)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return request-validation (422) errors as one clear, field-named sentence.

    FastAPI's default surfaces a raw list of terse messages with no field names, which
    reaches the user as a generic "Invalid input". Here we name the offending field and
    state the problem (e.g. "Items #1 → Quantity: must be a valid number") so the user
    knows exactly what to correct.
    """
    parts: list[str] = []
    seen: set[str] = set()
    for err in exc.errors():
        msg = str(err.get("msg") or "Invalid value")
        for old, new in _VALIDATION_MSG_REWRITES:
            msg = msg.replace(old, new)
        msg = msg.strip()
        field = _humanize_validation_location(tuple(err.get("loc", ())))
        entry = f"{field}: {msg}" if field else msg
        if entry not in seen:
            seen.add(entry)
            parts.append(entry)

    detail = "; ".join(parts) if parts else "Some fields are invalid. Please correct and try again."
    logger.info("Validation error on %s %s: %s", request.method, request.url.path, detail)
    return JSONResponse(status_code=422, content={"detail": detail, "path": request.url.path})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Return HTTPExceptions as JSON, upgrading the framework's bare 404 on API routes.

    An unmatched route makes Starlette raise `HTTPException(404, "Not Found")`. Surfaced
    verbatim, the UI shows a useless generic "Not Found" — which is exactly what happens
    when an endpoint exists in code but is missing from the deployed build (e.g. a feature
    branch not yet released to production). For API paths we replace only that default
    message with a clear, actionable one; explicit business 404s raised by endpoints
    (e.g. "GRN not found.") carry their own detail and are passed through unchanged, as
    are all non-404 HTTPExceptions (401/403/etc.) with their headers preserved.
    """
    detail = exc.detail
    is_unmatched_route = (
        exc.status_code == 404
        and request.url.path.startswith("/api/")
        and (detail is None or detail == "Not Found")
    )
    if is_unmatched_route:
        detail = (
            "This endpoint is unavailable on the server. It may require a pending "
            "deployment/update. Please contact your administrator if the problem persists."
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "path": request.url.path},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    message = str(getattr(exc, "orig", exc))
    lower = message.lower()
    
    # Log the full error for debugging
    logger.error(f"IntegrityError on {request.method} {request.url.path}: {message}")

    if "unique" in lower or "duplicate key value" in lower:
        # Field-specific message based on the violated constraint/column (safety net;
        # most flows pre-check and raise their own clear message first).
        detail = "This value already exists. Please use a unique value."
        if "gstin" in lower:
            detail = "GSTIN already exists."
        elif "tenant_code" in lower:
            detail = "Tenant Code already exists."
        elif "customer_code" in lower:
            detail = "Customer Code already exists."
        elif "supplier_code" in lower:
            detail = "Supplier Code already exists."
        elif "product_code" in lower:
            detail = "Product Code already exists. Please try again."
        elif "abbreviation" in lower:
            detail = "Unit abbreviation already exists."
        elif "contact_number" in lower or "contact" in lower:
            detail = "Contact Number already exists."
        elif "email" in lower:
            detail = "Email is already registered."
        elif "category" in lower and "name" in lower:
            detail = "Category Name already exists."
        elif "company" in lower and "name" in lower:
            detail = "Company Name already exists."
        elif "invoice_number" in lower:
            detail = "Invoice number already exists. Please retry."
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
    logger.error(
        "Unhandled server error on %s %s",
        request.method,
        request.url.path,
        exc_info=True,
        extra={"correlation_id": correlation_id.get()},
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
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
        "default": "v2",
        "supported": ["v1", "v2"],
        "v2_mode": "compatibility_alias_to_v1",
    }


@app.get("/api/v1")
@app.get("/api/v1/")
async def api_v1_root():
    """API v1 root endpoint."""
    return {
        "version": "v1",
        "status": "active",
    }


@app.get("/api/v2")
@app.get("/api/v2/")
async def api_v2_root():
    """API v2 root endpoint (compatibility mode mapped to v1 handlers)."""
    return {
        "version": "v2",
        "compatibility": "v1",
        "status": "active",
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": " Mecandria ERP API",
        "docs": "/docs",
        "version": "1.0.0",
    }
