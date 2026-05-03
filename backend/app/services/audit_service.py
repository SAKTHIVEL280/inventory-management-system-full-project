"""Audit logging utilities."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_SENSITIVE_TOKENS = {
    "password",
    "passwd",
    "token",
    "secret",
    "authorization",
    "cookie",
    "session",
    "api_key",
    "apikey",
}
_RETENTION_CHECK_INTERVAL_SECONDS = 3600
_last_retention_check_at = 0.0
_HTTP_ACTIONS = {"POST", "PUT", "PATCH", "DELETE", "GET", "VIEW", "REPORT"}

_ENTITY_LABELS = {
    "users": "User",
    "user": "User",
    "customers": "Customer",
    "customer": "Customer",
    "suppliers": "Supplier",
    "supplier": "Supplier",
    "products": "Product",
    "product": "Product",
    "purchase": "Purchase Order",
    "purchases": "Purchase Order",
    "sales": "Invoice",
    "invoices": "Invoice",
    "purchase-orders": "Purchase Order",
    "grn": "GRN",
    "payments": "Payment",
    "stock": "Stock Adjustment",
    "sales-returns": "Sales Return",
    "purchase-returns": "Purchase Return",
    "reports": "Report",
    "audit": "Action Log",
    "auth": "Session",
}

_FINANCIAL_MODULES = {
    "invoices",
    "purchase-orders",
    "grn",
    "payments",
    "stock",
    "sales-returns",
    "purchase-returns",
}


def _ensure_audit_logs_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id),
                username VARCHAR(255),
                action VARCHAR(120) NOT NULL,
                action_type VARCHAR(40) NOT NULL,
                module_name VARCHAR(80) NOT NULL,
                resource_type VARCHAR(80),
                resource_id UUID,
                record_reference VARCHAR(255),
                description TEXT,
                status VARCHAR(20) NOT NULL,
                details JSONB NOT NULL DEFAULT '{}'::jsonb,
                ip_address VARCHAR(64),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    db.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS username VARCHAR(255)"))
    db.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS action_type VARCHAR(40)"))
    db.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS module_name VARCHAR(80)"))
    db.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS record_reference VARCHAR(255)"))
    db.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS description TEXT"))
    db.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at)"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id)"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_module_name ON audit_logs (module_name)"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_action_type ON audit_logs (action_type)"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_record_reference ON audit_logs (record_reference)"))


def _is_sensitive_key(key: str) -> bool:
    token = (key or "").strip().lower()
    return any(fragment in token for fragment in _SENSITIVE_TOKENS)


def _sanitize_details(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if _is_sensitive_key(key):
                sanitized[key] = "***"
            else:
                sanitized[key] = _sanitize_details(v)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_details(v) for v in value]
    return value


def _derive_action_type(action: str) -> str:
    token = (action or "").strip()
    if not token:
        return "UNKNOWN"
    return token.split(":", 1)[0].strip().upper()


def _looks_like_uuid(value: str) -> bool:
    token = (value or "").strip()
    return bool(re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}", token))


def _extract_reference_from_action_path(action: str) -> str | None:
    if ":" not in (action or ""):
        return None
    action_type, raw_path = action.split(":", 1)
    if action_type.strip().upper() not in _HTTP_ACTIONS:
        return None

    path = (raw_path or "").strip()
    if not path.startswith("/api/"):
        return None

    segments = [segment for segment in path.strip("/").split("/") if segment]
    if len(segments) < 4 or segments[0] != "api" or segments[1] not in {"v1", "v2"}:
        return None

    resource_segment = segments[2]
    candidate = segments[-1]
    if candidate == resource_segment:
        return None
    if candidate in {"export", "bulk", "items", "status", "action-logs", "gst-audit-trail", "gstr1", "gstr2", "gstr3b", "gst-reconciliation"}:
        return None
    if _looks_like_uuid(candidate) or any(ch.isdigit() for ch in candidate):
        return candidate
    return None


def _entity_label(module_name: str, action_type: str, details: dict[str, Any]) -> str:
    token = (module_name or "system").strip().lower() or "system"
    report_type = str(details.get("report_type") or "").strip().lower()
    if "REPORT" in action_type or action_type in {"VIEW_ACTION_LOGS", "GENERATE_REPORT"} or token == "reports":
        if report_type == "gstr1":
            return "GSTR-1 Report"
        if report_type == "gstr2":
            return "GSTR-2 Report"
        if report_type == "gstr3b":
            return "GSTR-3B Report"
        if report_type == "reconciliation":
            return "GST Reconciliation Report"
        if action_type == "VIEW_ACTION_LOGS":
            return "Action Logs"
        return "GST Report"
    return _ENTITY_LABELS.get(token, token.replace("_", " ").title())


def _action_phrase(action_type: str) -> str:
    token = (action_type or "UNKNOWN").strip().upper()
    if token == "POST":
        return "Created"
    if token in {"PUT", "PATCH"}:
        return "Updated"
    if token == "DELETE":
        return "Deleted"
    if token in {"GET", "VIEW", "VIEW_ACTION_LOGS"} or token.startswith("VIEW"):
        return "Viewed"
    if token in {"REPORT", "GENERATE_REPORT"} or "REPORT" in token:
        return "Generated"
    if token == "LOGIN":
        return "Logged in"
    if token == "LOGOUT":
        return "Logged out"
    if token == "TOKEN_REFRESH":
        return "Refreshed"
    if token == "CHANGE_PASSWORD":
        return "Changed"
    return "Updated"


def _reference_display(record_reference: str | None, details: dict[str, Any]) -> str:
    name_keys = [
        "product_name",
        "customer_name",
        "supplier_name",
        "full_name",
        "name",
    ]
    for key in name_keys:
        raw = details.get(key)
        if raw is not None and str(raw).strip():
            return f'"{str(raw).strip()}"'
    return (record_reference or "").strip()


def _extract_document_reference(record_reference: str | None, details: dict[str, Any], db: Session | None = None, module_name: str | None = None) -> str:
    """Extract and display document numbers (invoice/PO/GRN) from audit details, DB lookup, or path."""
    # Priority order for document numbers in details
    doc_number_keys = [
        "invoice_number",
        "invoice_no",
        "sales_invoice_no",
        "po_number",
        "po_no",
        "purchase_order_no",
        "grn_number",
        "grn_no",
        "goods_receipt_no",
        "payment_number",
        "receipt_number",
        "count_number",
        "product_code",
        "customer_code",
        "supplier_code",
    ]
    
    if not isinstance(details, dict):
        details = {}
    
    # First try to find a document number in details
    for key in doc_number_keys:
        value = details.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    
    # Extract UUID from path if available
    path = (details.get("path") or "").strip()
    resource_uuid = None
    
    if path:
        segments = [segment for segment in path.strip("/").split("/") if segment]
        # Look for UUID in path segments
        for segment in segments:
            if _looks_like_uuid(segment):
                resource_uuid = segment
                break
        
        # If no UUID found, check for document reference patterns
        if not resource_uuid and len(segments) >= 3:
            # Check last segment first
            candidate = segments[-1]
            # Skip common action suffixes
            skip_suffixes = {"export", "bulk", "items", "status", "action-logs", "create", "update", "delete", "page", "confirm", "issue", "send-email"}
            if candidate.lower() not in skip_suffixes and not candidate.isdigit():
                # Document references typically have letters and hyphens (e.g., INV-001, PO-002, GRN-001)
                if candidate and any(ch.isalpha() for ch in candidate) and ("-" in candidate or any(ch.isdigit() for ch in candidate)):
                    return candidate
            
            # Try second-to-last segment (in case last is an action)
            if len(segments) >= 4:
                candidate = segments[-2]
                if candidate.lower() not in skip_suffixes and not candidate.isdigit():
                    if candidate and any(ch.isalpha() for ch in candidate) and ("-" in candidate or any(ch.isdigit() for ch in candidate)):
                        return candidate
    
    # Try to fetch from database using UUID from path or record_reference
    if db and module_name:
        uuid_to_lookup = resource_uuid or (record_reference if record_reference and _looks_like_uuid(record_reference) else None)
        if uuid_to_lookup:
            try:
                ref = _fetch_document_reference_from_db(db, module_name.strip().lower(), uuid_to_lookup)
                if ref:
                    return ref
            except Exception as e:
                logger.debug(f"Failed to fetch reference from DB for {module_name}:{uuid_to_lookup}: {e}")
    
    # Fall back to record_reference if it's not a UUID or module name
    if record_reference and not _looks_like_uuid(record_reference):
        # Don't show module names as references
        module_names = {"invoices", "purchase-orders", "grn", "payments", "stock", "customers", "suppliers", "products", "users", "quotations"}
        if record_reference.lower() not in module_names:
            return record_reference.strip()
    
    return ""


def _fetch_document_reference_from_db(db: Session, module_name: str, resource_id: str) -> str | None:
    """Fetch the actual document reference number from database based on module and resource ID.
    
    Uses exact field names from schema:
    - sales_invoices.invoice_number
    - purchase_orders.po_number
    - goods_receipt_notes.grn_number
    - quotations.quotation_number
    - payments.payment_number
    - inventory_counts.count_number
    - products.product_code
    """
    module = (module_name or "").strip().lower()
    
    try:
        # Sales invoices (invoices module)
        if module in {"invoices", "sales", "sales-invoices"}:
            result = db.execute(
                text("SELECT invoice_number FROM sales_invoices WHERE id = :id AND is_deleted = FALSE LIMIT 1"),
                {"id": resource_id}
            ).scalar()
            if result:
                return str(result).strip()
        
        # Quotations
        elif module in {"quotations", "quotation"}:
            result = db.execute(
                text("SELECT quotation_number FROM quotations WHERE id = :id AND is_deleted = FALSE LIMIT 1"),
                {"id": resource_id}
            ).scalar()
            if result:
                return str(result).strip()
        
        # Purchase orders
        elif module in {"purchase-orders", "purchase_orders", "purchase"}:
            result = db.execute(
                text("SELECT po_number FROM purchase_orders WHERE id = :id AND is_deleted = FALSE LIMIT 1"),
                {"id": resource_id}
            ).scalar()
            if result:
                return str(result).strip()
        
        # GRN (Goods Receipt Notes)
        elif module in {"grn", "goods-receipt", "goods_receipt"}:
            result = db.execute(
                text("SELECT grn_number FROM goods_receipt_notes WHERE id = :id AND is_deleted = FALSE LIMIT 1"),
                {"id": resource_id}
            ).scalar()
            if result:
                return str(result).strip()
        
        # Payments - return payment number with related invoice/GRN and status
        elif module in {"payments", "payment"}:
            payment = db.execute(
                text("""
                    SELECT p.payment_number, p.status, p.payment_type, p.party_type
                    FROM payments p
                    WHERE p.id = :id AND p.is_deleted = FALSE
                    LIMIT 1
                """),
                {"id": resource_id}
            ).mappings().first()
            
            if payment:
                payment_num = payment.get("payment_number")
                status = (payment.get("status") or "").strip().lower()
                payment_type = (payment.get("payment_type") or "").strip().lower()
                party_type = (payment.get("party_type") or "").strip().lower()
                
                # Try to get related invoice or GRN from allocations
                allocation = db.execute(
                    text("""
                        SELECT si.invoice_number, grn.grn_number
                        FROM payment_allocations pa
                        LEFT JOIN sales_invoices si ON pa.invoice_id = si.id AND si.is_deleted = FALSE
                        LEFT JOIN goods_receipt_notes grn ON pa.purchase_grn_id = grn.id AND grn.is_deleted = FALSE
                        WHERE pa.payment_id = :payment_id AND pa.is_deleted = FALSE
                        LIMIT 1
                    """),
                    {"payment_id": resource_id}
                ).mappings().first()
                
                if allocation:
                    invoice_num = allocation.get("invoice_number")
                    grn_num = allocation.get("grn_number")
                    
                    # Build reference with document number and status
                    if invoice_num:
                        status_label = _payment_status_label(status)
                        if status_label:
                            return f"{invoice_num} ({status_label})"
                        return str(invoice_num).strip()
                    
                    elif grn_num:
                        status_label = _payment_status_label(status)
                        if status_label:
                            return f"{grn_num} ({status_label})"
                        return str(grn_num).strip()
                
                # Fallback to payment number with type/status
                if payment_num:
                    parts = [str(payment_num).strip()]
                    if payment_type == "receipt":
                        parts.append("Receipt")
                    elif payment_type == "payment":
                        parts.append("Payment")
                    
                    status_label = _payment_status_label(status)
                    if status_label:
                        parts.append(f"({status_label})")
                    
                    return " ".join(parts)
        
        # Stock/Inventory adjustments - show count number or product code with reason
        elif module in {"stock", "inventory-count", "inventory_count", "inventory_counts"}:
            # First try to get inventory count number
            result = db.execute(
                text("SELECT count_number FROM inventory_counts WHERE id = :id AND is_deleted = FALSE LIMIT 1"),
                {"id": resource_id}
            ).scalar()
            if result:
                return str(result).strip()
            
            # Try to get from inventory count difference audit (for stock adjustments)
            audit = db.execute(
                text("""
                    SELECT icda.count_number, icda.reason_label, p.product_code
                    FROM inventory_count_difference_audits icda
                    LEFT JOIN products p ON icda.product_id = p.id
                    WHERE icda.id = :id
                    LIMIT 1
                """),
                {"id": resource_id}
            ).mappings().first()
            
            if audit:
                product_code = audit.get("product_code")
                reason = audit.get("reason_label")
                count_num = audit.get("count_number")
                
                if product_code and reason:
                    return f"{product_code} - {reason}"
                elif count_num:
                    return str(count_num).strip()
            
            # Fallback: try to get product code from stock ledger
            ledger = db.execute(
                text("""
                    SELECT p.product_code, sl.transaction_type, sl.reference_number
                    FROM stock_ledger sl
                    LEFT JOIN products p ON sl.product_id = p.id
                    WHERE sl.id = :id AND sl.is_deleted = FALSE
                    LIMIT 1
                """),
                {"id": resource_id}
            ).mappings().first()
            
            if ledger:
                product_code = ledger.get("product_code")
                ref_num = ledger.get("reference_number")
                txn_type = (ledger.get("transaction_type") or "").strip().lower()
                
                if ref_num:
                    return str(ref_num).strip()
                elif product_code:
                    type_label = txn_type.replace("_", " ").title() if txn_type else "Adjustment"
                    return f"{product_code} - {type_label}"
        
        # Customers
        elif module in {"customers", "customer"}:
            result = db.execute(
                text("SELECT company_name FROM customers WHERE id = :id AND is_deleted = FALSE LIMIT 1"),
                {"id": resource_id}
            ).scalar()
            if result:
                return str(result).strip()
        
        # Suppliers
        elif module in {"suppliers", "supplier"}:
            result = db.execute(
                text("SELECT company_name FROM suppliers WHERE id = :id AND is_deleted = FALSE LIMIT 1"),
                {"id": resource_id}
            ).scalar()
            if result:
                return str(result).strip()
        
        # Products
        elif module in {"products", "product"}:
            result = db.execute(
                text("SELECT product_code FROM products WHERE id = :id AND is_deleted = FALSE LIMIT 1"),
                {"id": resource_id}
            ).scalar()
            if result:
                return str(result).strip()
        
        # Users
        elif module in {"users", "user"}:
            result = db.execute(
                text("SELECT email FROM users WHERE id = :id LIMIT 1"),
                {"id": resource_id}
            ).scalar()
            if result:
                return str(result).strip()
        
    except Exception as e:
        logger.debug(f"Error fetching reference from DB for {module}:{resource_id}: {e}")
    
    return None


def _payment_status_label(status: str) -> str:
    """Convert payment status to human-readable label."""
    status_lower = (status or "").strip().lower()
    
    if status_lower in {"pending", "draft"}:
        return "Pending"
    elif status_lower == "cleared":
        return "Cleared"
    elif status_lower == "bounced":
        return "Bounced"
    elif status_lower == "cancelled":
        return "Cancelled"
    
    return ""


def _build_human_readable_description(
    *,
    action_type: str,
    module_name: str,
    record_reference: str | None,
    details: dict[str, Any],
) -> str:
    phrase = _action_phrase(action_type)
    entity = _entity_label(module_name, action_type, details)
    reference = _reference_display(record_reference, details)

    token = (action_type or "").strip().upper()
    if token == "LOGIN":
        return "Logged in"
    if token == "LOGOUT":
        return "Logged out"
    if token == "TOKEN_REFRESH":
        return "Refreshed session"
    if token == "CHANGE_PASSWORD":
        return "Changed password"

    # Check for specific actions in the path
    path = (details.get("path") or "").strip().lower()
    
    # GRN confirm action
    if "grn" in module_name.lower() and "/confirm" in path:
        return f"Confirmed {entity}"
    
    # Invoice issue action
    if "invoice" in module_name.lower() and "/issue" in path:
        return f"Issued {entity}"
    
    # Payment status update
    if "payment" in module_name.lower() and "/status" in path:
        return f"Updated {entity} status"
    
    # Stock adjustment accept
    if "stock" in module_name.lower() and "/accept" in path:
        return f"Accepted stock adjustment"
    
    # Generic action descriptions
    if token == "POST":
        base = f"Created {entity}"
    elif token in {"REPORT", "GENERATE_REPORT"} or "REPORT" in token:
        base = f"Generated {entity}"
    else:
        base = f"{phrase} {entity}"

    if reference:
        return f"{base} {reference}".strip()
    return base


def _derive_record_reference(resource_id: UUID | str | None, details: dict[str, Any], action: str) -> str | None:
    preferred_keys = [
        "record_reference",
        "reference",
        "invoice_number",
        "invoice_no",
        "sales_invoice_no",
        "po_number",
        "po_no",
        "grn_number",
        "grn_no",
        "payment_number",
        "receipt_number",
        "count_number",
        "product_code",
        "customer_code",
        "supplier_code",
    ]
    for key in preferred_keys:
        value = details.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    path_reference = _extract_reference_from_action_path(action)
    if path_reference:
        return path_reference
    if resource_id:
        return str(resource_id)
    return None


def _maybe_cleanup_old_audit_logs(db: Session) -> None:
    global _last_retention_check_at
    now = time.monotonic()
    if now - _last_retention_check_at < _RETENTION_CHECK_INTERVAL_SECONDS:
        return
    _last_retention_check_at = now

    retention_days = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "365") or "365")
    if retention_days <= 0:
        return

    db.execute(
        text(
            """
            DELETE FROM audit_logs
            WHERE created_at < NOW() - (:retention_days::text || ' days')::interval
            """
        ),
        {"retention_days": retention_days},
    )


def ensure_audit_logs_storage(db: Session) -> None:
    """Public helper for endpoints that need guaranteed audit table availability."""
    _ensure_audit_logs_table(db)


def log_audit_event(
    db: Session,
    *,
    action: str,
    resource_type: str,
    status: str,
    user_id: UUID | str | None = None,
    resource_id: UUID | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Write a best-effort audit event.

    This function must never break request flow, so failures are swallowed.
    """
    try:
        _ensure_audit_logs_table(db)

        safe_details = _sanitize_details(details or {})
        action_type = _derive_action_type(action)
        module_name = (resource_type or "system").strip().lower() or "system"
        if module_name not in _FINANCIAL_MODULES:
            return
        safe_detail_dict = safe_details if isinstance(safe_details, dict) else {}
        record_reference = _derive_record_reference(resource_id, safe_detail_dict, action)
        description = _build_human_readable_description(
            action_type=action_type,
            module_name=module_name,
            record_reference=record_reference,
            details=safe_detail_dict,
        )
        username = ""
        if isinstance(safe_details, dict):
            username = str(
                safe_details.get("username")
                or safe_details.get("user_name")
                or safe_details.get("email")
                or ""
            ).strip()

        with db.begin_nested():
            db.execute(
                text(
                    """
                    INSERT INTO audit_logs (
                        user_id, username, action, action_type, module_name, resource_type, resource_id,
                        record_reference, description, status, details, ip_address
                    ) VALUES (
                        :user_id, :username, :action, :action_type, :module_name, :resource_type, :resource_id,
                        :record_reference, :description, :status, CAST(:details AS JSONB), :ip_address
                    )
                    """
                ),
                {
                    "user_id": str(user_id) if user_id else None,
                    "username": username or None,
                    "action": action,
                    "action_type": action_type,
                    "module_name": module_name,
                    "resource_type": resource_type,
                    "resource_id": str(resource_id) if resource_id else None,
                    "record_reference": record_reference,
                    "description": description,
                    "status": status,
                    "details": json.dumps(safe_details),
                    "ip_address": ip_address,
                },
            )
            _maybe_cleanup_old_audit_logs(db)
        logger.info(
            "AUDIT action=%s action_type=%s module=%s status=%s user_id=%s reference=%s",
            action,
            action_type,
            module_name,
            status,
            str(user_id) if user_id else "anonymous",
            record_reference or "-",
        )
    except Exception:
        # Best-effort logging should not interrupt business flow.
        return
