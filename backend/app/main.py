"""Main FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import auth, company, users, customers, suppliers, products, purchase, sales, payments, reports

app = FastAPI(
    title="Inventory Management System",
    description="Complete inventory management with GST-aware purchase, sales, and reporting",
    version="1.0.0",
)

# CORS configuration - MUST BE ADDED FIRST
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    settings.frontend_url,
]

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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Inventory Management System API",
        "docs": "/docs",
        "version": "1.0.0",
    }
