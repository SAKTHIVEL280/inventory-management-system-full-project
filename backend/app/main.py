"""Main FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import auth, company, users, customers, suppliers, products, purchase, sales, payments, reports, stock
from fastapi.staticfiles import StaticFiles
import os

# Create static directory if it doesn't exist
os.makedirs("static", exist_ok=True)

app = FastAPI(
    title="Inventory Management System",
    description="Complete inventory management with GST-aware purchase, sales, and reporting",
    version="1.0.0",
)

# Mount static files for company logo and assets
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS configuration - MUST BE ADDED FIRST
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    settings.frontend_url,
]
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
