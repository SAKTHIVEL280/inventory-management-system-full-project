"""Subscription plan configuration (Super Admin → Plan Configuration).

One row per subscription tier (FREE / SILVER / GOLD / PLATINUM). Holds the
DB-backed, Super-Admin-editable definition of what each plan is entitled to:
display name, pricing, billing period, user limit, module access, feature access
and active/inactive status. This replaces the previously hardcoded plan matrix in
`plan_service.py` (which now reads from this table with a code-level fallback).

Changes here take effect immediately for every tenant on the plan: `plan_service`
caches these rows and the cache is invalidated whenever a plan is saved.
"""
from uuid import uuid4
from datetime import datetime

from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, UUID
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Canonical, immutable plan identifier (FREE/SILVER/GOLD/PLATINUM). Uppercase.
    plan_key = Column(String(20), nullable=False, unique=True, index=True)

    # Editable display name shown to tenants and on invoices.
    name = Column(String(80), nullable=False)

    # Pricing in paise (integer, avoids float rounding). billing_period is the
    # recurrence the price applies to: 'monthly' | 'yearly' | 'none' (free tier).
    price_paise = Column(BigInteger, nullable=False, default=0)
    billing_period = Column(String(20), nullable=False, default="monthly")

    # Maximum ACTIVE user accounts allowed on the plan.
    user_limit = Column(Integer, nullable=False, default=1)

    # Module keys the plan grants (subset of plan_service.MODULE_CATALOG keys).
    modules = Column(JSONB, nullable=False, default=list)
    # LEGACY / UNUSED: features are now DERIVED from `modules` (plan_service.
    # derive_features) and are no longer configured or read from this column. Kept
    # for backward compatibility; safe to drop in a future migration.
    features = Column(JSONB, nullable=False, default=list)
    # Assignable user-role families for the plan (BRD §6).
    roles = Column(JSONB, nullable=False, default=list)

    # FREE-tier monthly service-invoice cap (NULL = unlimited / not applicable).
    free_invoice_cap = Column(Integer, nullable=True)

    # Active plans may be assigned to tenants; inactive plans are retired (existing
    # tenants keep working, but the plan can no longer be assigned to a tenant).
    is_active = Column(Boolean, nullable=False, default=True)

    # Display ordering in the configuration matrix (FREE→PLATINUM).
    sort_order = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
