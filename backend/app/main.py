"""Main FastAPI application."""
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.routers import auth, company, users, customers, suppliers, products, purchase, sales, payments, reports, stock, archive
from fastapi.staticfiles import StaticFiles
import os

logger = logging.getLogger(__name__)

# Create static directory if it doesn't exist
os.makedirs("static", exist_ok=True)

app = FastAPI(
    title=" Mecandria ERP",
    description="Complete inventory management with GST-aware purchase, sales, and reporting",
    version="1.0.0",
)

# Mount static files for company logo and assets
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS configuration - MUST BE ADDED FIRST
allowed_origins = list(
    dict.fromkeys(
        [
            "http://localhost:3001",
            "http://127.0.0.1:3001",
            settings.frontend_url,
        ]
    )
)
# For development, we can also use allow_origin_regex or just "*" if we trust the environment
# app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
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
        content={"detail": f"Database constraint violation: {message}", "path": request.url.path},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
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


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": " Mecandria ERP API",
        "docs": "/docs",
        "version": "1.0.0",
    }
