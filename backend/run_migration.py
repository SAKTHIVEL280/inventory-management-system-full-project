"""Idempotent compatibility migration for existing databases.

This script keeps older DBs compatible with current SQLAlchemy models.
Run safely multiple times.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, text


def _load_database_url() -> str:
    # Prefer environment first
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        return env_url

    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "DATABASE_URL":
                return value.strip().strip('"').strip("'")

    # Last resort for local development compatibility
    return "postgresql://postgres:root@localhost:5432/ims_db"


def main() -> int:
    database_url = _load_database_url()
    engine = create_engine(database_url)

    statements = [
        # Ensure UUID generator exists
        "CREATE EXTENSION IF NOT EXISTS \"pgcrypto\"",

        # Auth hardening fields
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ NULL",
        "UPDATE users SET email = regexp_replace(email, '@local\\.invalid$', '@example.com') WHERE email ~* '@local\\.invalid$'",

        # Tenant scoping fields for IDOR protection
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_id UUID",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS company_id UUID",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS company_id UUID",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS company_id UUID",
        "CREATE INDEX IF NOT EXISTS ix_users_company_id ON users (company_id)",
        "CREATE INDEX IF NOT EXISTS ix_products_company_id ON products (company_id)",
        "CREATE INDEX IF NOT EXISTS ix_customers_company_id ON customers (company_id)",
        "CREATE INDEX IF NOT EXISTS ix_suppliers_company_id ON suppliers (company_id)",
        """
        DO $$
        DECLARE company_uuid UUID;
        BEGIN
            SELECT id INTO company_uuid
            FROM company
            ORDER BY created_at ASC
            LIMIT 1;

            IF company_uuid IS NOT NULL THEN
                UPDATE users
                SET company_id = company_uuid
                WHERE company_id IS NULL;

                UPDATE products p
                SET company_id = COALESCE(
                    (SELECT u.company_id FROM users u WHERE u.id = p.created_by),
                    company_uuid
                )
                WHERE p.company_id IS NULL;

                UPDATE customers c
                SET company_id = COALESCE(
                    (SELECT u.company_id FROM users u WHERE u.id = c.created_by),
                    company_uuid
                )
                WHERE c.company_id IS NULL;

                UPDATE suppliers s
                SET company_id = COALESCE(
                    (SELECT u.company_id FROM users u WHERE u.id = s.created_by),
                    company_uuid
                )
                WHERE s.company_id IS NULL;
            END IF;
        END $$
        """,
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_users_company') THEN
                ALTER TABLE users
                    ADD CONSTRAINT fk_users_company
                    FOREIGN KEY (company_id) REFERENCES company(id);
            END IF;
        END $$
        """,
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_products_company') THEN
                ALTER TABLE products
                    ADD CONSTRAINT fk_products_company
                    FOREIGN KEY (company_id) REFERENCES company(id);
            END IF;
        END $$
        """,
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_customers_company') THEN
                ALTER TABLE customers
                    ADD CONSTRAINT fk_customers_company
                    FOREIGN KEY (company_id) REFERENCES company(id);
            END IF;
        END $$
        """,
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_suppliers_company') THEN
                ALTER TABLE suppliers
                    ADD CONSTRAINT fk_suppliers_company
                    FOREIGN KEY (company_id) REFERENCES company(id);
            END IF;
        END $$
        """,

        # Inventory/model compatibility
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS safety_stock INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'active'",
        "ALTER TABLE products DROP CONSTRAINT IF EXISTS products_sku_key",
        """
        DO $$
        DECLARE idx_name TEXT;
        BEGIN
            FOR idx_name IN
                SELECT i.relname
                FROM pg_class t
                JOIN pg_index x ON t.oid = x.indrelid
                JOIN pg_class i ON i.oid = x.indexrelid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(x.indkey)
                WHERE t.relname = 'products'
                  AND x.indisunique = TRUE
                  AND a.attname = 'sku'
            LOOP
                EXECUTE format('DROP INDEX IF EXISTS %I', idx_name);
            END LOOP;
        END $$
        """,
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS place_of_supply VARCHAR(255)",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255)",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255)",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered'",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS business_type VARCHAR(20) NOT NULL DEFAULT 'domestic'",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS billing_country VARCHAR(100)",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS business_type VARCHAR(20) NOT NULL DEFAULT 'domestic'",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS billing_country VARCHAR(100)",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS currency_code VARCHAR(10) NOT NULL DEFAULT 'INR'",
        "ALTER TABLE company ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered'",
        "ALTER TABLE company ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255)",
        "ALTER TABLE company ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255)",
        "ALTER TABLE company ADD COLUMN IF NOT EXISTS account_holder_name VARCHAR(255)",
        "ALTER TABLE company ADD COLUMN IF NOT EXISTS country VARCHAR(100)",
        "ALTER TABLE company ADD COLUMN IF NOT EXISTS ambassador_logo_url VARCHAR(500)",

        # Currency support
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS currency_code VARCHAR(10) NOT NULL DEFAULT 'INR'",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255)",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255)",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered'",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS business_type VARCHAR(20) NOT NULL DEFAULT 'domestic'",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS billing_country VARCHAR(100)",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS shipping_country VARCHAR(100)",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS business_type VARCHAR(20) NOT NULL DEFAULT 'domestic'",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS billing_country VARCHAR(100)",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS shipping_country VARCHAR(100)",
        "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS currency_code VARCHAR(3) NOT NULL DEFAULT 'INR'",
        "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(12, 6) NOT NULL DEFAULT 1.0",
        "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS under_delivery_tolerance NUMERIC(10, 2) NOT NULL DEFAULT 0",
        "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS over_delivery_tolerance NUMERIC(10, 2) NOT NULL DEFAULT 0",
        "ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS currency_code VARCHAR(3) NOT NULL DEFAULT 'INR'",
        "ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(12, 6) NOT NULL DEFAULT 1.0",

        # GRN batch tracking fields
        "ALTER TABLE goods_receipt_notes ADD COLUMN IF NOT EXISTS payment_due_date DATE",
        "ALTER TABLE goods_receipt_notes ADD COLUMN IF NOT EXISTS under_delivery_tolerance NUMERIC(10, 2) NOT NULL DEFAULT 0",
        "ALTER TABLE goods_receipt_notes ADD COLUMN IF NOT EXISTS over_delivery_tolerance NUMERIC(10, 2) NOT NULL DEFAULT 0",
        "ALTER TABLE grn_items ADD COLUMN IF NOT EXISTS batch_no VARCHAR(100)",
        "ALTER TABLE grn_items ADD COLUMN IF NOT EXISTS manufacture_date DATE",
        "ALTER TABLE grn_items ADD COLUMN IF NOT EXISTS expiry_date DATE",
        "ALTER TABLE grn_items ADD COLUMN IF NOT EXISTS free_quantity NUMERIC(12, 4) NOT NULL DEFAULT 0",

        # MCN-BUG-004: Reverse GRN support
        "ALTER TABLE goods_receipt_notes DROP CONSTRAINT IF EXISTS goods_receipt_notes_status_check",
        "ALTER TABLE goods_receipt_notes ADD CONSTRAINT goods_receipt_notes_status_check CHECK (status IN ('draft','confirmed','cancelled','reversed'))",
        "ALTER TABLE goods_receipt_notes ADD COLUMN IF NOT EXISTS reversal_reason TEXT",
        "ALTER TABLE goods_receipt_notes ADD COLUMN IF NOT EXISTS reversed_at TIMESTAMPTZ",
        "ALTER TABLE goods_receipt_notes ADD COLUMN IF NOT EXISTS reversed_by UUID REFERENCES users(id)",

        # Sales invoice item extended fields
        "ALTER TABLE sales_invoice_items ADD COLUMN IF NOT EXISTS order_unit VARCHAR(50)",
        "ALTER TABLE sales_invoice_items ADD COLUMN IF NOT EXISTS batch_no VARCHAR(50)",
        "ALTER TABLE sales_invoice_items ADD COLUMN IF NOT EXISTS manufacture_date DATE",
        "ALTER TABLE sales_invoice_items ADD COLUMN IF NOT EXISTS expiry_date DATE",
        "ALTER TABLE sales_invoice_items ADD COLUMN IF NOT EXISTS free_quantity NUMERIC(12, 4) NOT NULL DEFAULT 0",
        "ALTER TABLE sales_invoices ADD COLUMN IF NOT EXISTS invoice_type VARCHAR(30) NOT NULL DEFAULT 'within_state'",
        "ALTER TABLE sales_invoices ADD COLUMN IF NOT EXISTS import_export_code VARCHAR(50)",
        "ALTER TABLE sales_invoices DROP CONSTRAINT IF EXISTS sales_invoices_status_check",
        "ALTER TABLE sales_invoices ADD CONSTRAINT sales_invoices_status_check CHECK (status IN ('draft','issued','partial_paid','paid','returned','cancelled'))",
        # Enhancement 3: Sales Invoice internal fields (Stockist / Sales Manager)
        "ALTER TABLE sales_invoices ADD COLUMN IF NOT EXISTS stockist_name VARCHAR(150)",
        "ALTER TABLE sales_invoices ADD COLUMN IF NOT EXISTS stockist_city VARCHAR(120)",
        "ALTER TABLE sales_invoices ADD COLUMN IF NOT EXISTS sales_manager_name VARCHAR(150)",
        "CREATE INDEX IF NOT EXISTS ix_sales_invoices_stockist_name ON sales_invoices (stockist_name)",
        "CREATE INDEX IF NOT EXISTS ix_sales_invoices_sales_manager_name ON sales_invoices (sales_manager_name)",
        # Enhancement 3: Stockist & Sales Manager master tables (Customization)
        """
        CREATE TABLE IF NOT EXISTS stockists (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(150) NOT NULL,
            city VARCHAR(120),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            company_id UUID REFERENCES company(id),
            created_by UUID REFERENCES users(id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_stockists_name ON stockists (name)",
        "CREATE INDEX IF NOT EXISTS ix_stockists_company_id ON stockists (company_id)",
        """
        CREATE TABLE IF NOT EXISTS sales_managers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(150) NOT NULL,
            employee_id VARCHAR(50),
            region VARCHAR(120),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            company_id UUID REFERENCES company(id),
            created_by UUID REFERENCES users(id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_sales_managers_name ON sales_managers (name)",
        "CREATE INDEX IF NOT EXISTS ix_sales_managers_company_id ON sales_managers (company_id)",
        "ALTER TABLE company ADD COLUMN IF NOT EXISTS import_export_number VARCHAR(50)",
        "ALTER TABLE company ADD COLUMN IF NOT EXISTS rdn_prefix VARCHAR(10) NOT NULL DEFAULT 'RDN'",
        "ALTER TABLE company ADD COLUMN IF NOT EXISTS rdn_counter INTEGER NOT NULL DEFAULT 1",

        # Return Delivery Notes (RDN)
        """
        CREATE TABLE IF NOT EXISTS return_delivery_notes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            rdn_number VARCHAR(30) UNIQUE NOT NULL,
            customer_id UUID NOT NULL REFERENCES customers(id),
            sales_invoice_id UUID NOT NULL REFERENCES sales_invoices(id),
            customer_delivery_number VARCHAR(50),
            customer_delivery_date DATE NOT NULL,
            receipt_date DATE NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','confirmed','cancelled')),
            notes TEXT,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            company_id UUID REFERENCES company(id),
            created_by UUID REFERENCES users(id),
            confirmed_by UUID REFERENCES users(id),
            confirmed_at TIMESTAMPTZ,
            cancelled_by UUID REFERENCES users(id),
            cancelled_at TIMESTAMPTZ
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS return_delivery_note_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            rdn_id UUID NOT NULL REFERENCES return_delivery_notes(id) ON DELETE CASCADE,
            product_id UUID NOT NULL REFERENCES products(id),
            invoice_item_id UUID REFERENCES sales_invoice_items(id),
            batch_no VARCHAR(100) NOT NULL,
            manufacture_date DATE NOT NULL,
            expiry_date DATE NOT NULL,
            invoice_quantity NUMERIC(12,4) NOT NULL,
            return_quantity NUMERIC(12,4) NOT NULL,
            mrp INTEGER,
            reason_code VARCHAR(120) NOT NULL,
            reason_label VARCHAR(150) NOT NULL,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_rdn_number ON return_delivery_notes (rdn_number)",
        "CREATE INDEX IF NOT EXISTS ix_rdn_customer_id ON return_delivery_notes (customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_rdn_invoice_id ON return_delivery_notes (sales_invoice_id)",
        "CREATE INDEX IF NOT EXISTS ix_rdn_items_rdn_id ON return_delivery_note_items (rdn_id)",
        "CREATE INDEX IF NOT EXISTS ix_rdn_items_product_id ON return_delivery_note_items (product_id)",

        # RDN Credit Notes
        """
        CREATE TABLE IF NOT EXISTS rdn_credit_notes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            credit_note_number VARCHAR(30) UNIQUE NOT NULL,
            rdn_id UUID NOT NULL REFERENCES return_delivery_notes(id) ON DELETE CASCADE,
            sales_invoice_id UUID NOT NULL REFERENCES sales_invoices(id),
            customer_id UUID NOT NULL REFERENCES customers(id),
            credit_note_date DATE NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'posted' CHECK (status IN ('draft','posted','cancelled')),
            subtotal INTEGER NOT NULL DEFAULT 0,
            total_discount INTEGER NOT NULL DEFAULT 0,
            total_taxable_amount INTEGER NOT NULL DEFAULT 0,
            total_cgst INTEGER NOT NULL DEFAULT 0,
            total_sgst INTEGER NOT NULL DEFAULT 0,
            total_igst INTEGER NOT NULL DEFAULT 0,
            total_gst INTEGER NOT NULL DEFAULT 0,
            total_amount INTEGER NOT NULL DEFAULT 0,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            company_id UUID REFERENCES company(id),
            created_by UUID REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS rdn_credit_note_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            credit_note_id UUID NOT NULL REFERENCES rdn_credit_notes(id) ON DELETE CASCADE,
            product_id UUID NOT NULL REFERENCES products(id),
            invoice_item_id UUID REFERENCES sales_invoice_items(id),
            return_quantity NUMERIC(12,4) NOT NULL,
            unit_price INTEGER NOT NULL,
            mrp INTEGER,
            discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
            discount_amount INTEGER NOT NULL DEFAULT 0,
            taxable_amount INTEGER NOT NULL,
            gst_rate INTEGER NOT NULL,
            cgst_amount INTEGER NOT NULL DEFAULT 0,
            sgst_amount INTEGER NOT NULL DEFAULT 0,
            igst_amount INTEGER NOT NULL DEFAULT 0,
            total_amount INTEGER NOT NULL,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_rdn_credit_note_number ON rdn_credit_notes (credit_note_number)",
        "CREATE INDEX IF NOT EXISTS ix_rdn_credit_notes_rdn_id ON rdn_credit_notes (rdn_id)",
        "CREATE INDEX IF NOT EXISTS ix_rdn_credit_notes_invoice_id ON rdn_credit_notes (sales_invoice_id)",
        "CREATE INDEX IF NOT EXISTS ix_rdn_credit_note_items_note_id ON rdn_credit_note_items (credit_note_id)",
        "CREATE INDEX IF NOT EXISTS ix_rdn_credit_note_items_product_id ON rdn_credit_note_items (product_id)",

        # Inventory count modules (STO-006 / STO-007)
        """
        CREATE TABLE IF NOT EXISTS inventory_counts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            count_number VARCHAR(30) UNIQUE NOT NULL,
            count_date DATE NOT NULL,
            count_performed_by VARCHAR(150) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'confirmed' CHECK (status IN ('draft','confirmed','cancelled')),
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            created_by UUID REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS inventory_count_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            inventory_count_id UUID NOT NULL REFERENCES inventory_counts(id) ON DELETE CASCADE,
            serial_number INTEGER NOT NULL,
            product_id UUID NOT NULL REFERENCES products(id),
            product_description TEXT,
            quantity NUMERIC(12,4) NOT NULL,
            batch_no VARCHAR(100),
            manufacture_date DATE,
            expiry_date DATE,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_inventory_counts_count_number ON inventory_counts (count_number)",
        "CREATE INDEX IF NOT EXISTS ix_inventory_count_items_count_id ON inventory_count_items (inventory_count_id)",
        "CREATE INDEX IF NOT EXISTS ix_inventory_count_items_product_id ON inventory_count_items (product_id)",
        """
        CREATE TABLE IF NOT EXISTS inventory_count_difference_audits (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            inventory_count_id UUID NOT NULL REFERENCES inventory_counts(id),
            inventory_count_item_id UUID NOT NULL REFERENCES inventory_count_items(id),
            count_number VARCHAR(30) NOT NULL,
            product_id UUID NOT NULL REFERENCES products(id),
            old_qty NUMERIC(12,4) NOT NULL,
            new_qty NUMERIC(12,4) NOT NULL,
            difference_qty NUMERIC(12,4) NOT NULL,
            reason_code VARCHAR(50) NOT NULL,
            reason_label VARCHAR(120) NOT NULL,
            accepted_by UUID NOT NULL REFERENCES users(id),
            accepted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_inventory_count_difference_audits_count_id ON inventory_count_difference_audits (inventory_count_id)",
        "CREATE INDEX IF NOT EXISTS ix_inventory_count_difference_audits_accepted_at ON inventory_count_difference_audits (accepted_at)",

        # Customer payment terms should be optional (DB-40)
        "ALTER TABLE customers ALTER COLUMN payment_terms_days DROP DEFAULT",
        "ALTER TABLE customers ALTER COLUMN payment_terms_days DROP NOT NULL",

                # Customer country/currency customization options
                """
                CREATE TABLE IF NOT EXISTS customization_options (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        module VARCHAR(50) NOT NULL,
                        field_name VARCHAR(50) NOT NULL,
                        option_value VARCHAR(120) NOT NULL,
                        display_label VARCHAR(150),
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                        deleted_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW(),
                        created_by UUID REFERENCES users(id)
                )
                """,
                # NOTE: the GLOBAL unique (module, field_name, option_value) is intentionally
                # NOT created here. customization_options is tenant-scoped (DB-215): the correct
                # PER-TENANT unique ux_customization_options_company_scope (company_id, module,
                # field_name, option_value) is created further below, after company_id is added
                # and backfilled. Creating the global unique here would fail on multi-tenant DBs
                # where two tenants legitimately share a value (e.g. customer/state/Karnataka).
                "CREATE INDEX IF NOT EXISTS ix_customization_options_module ON customization_options (module)",
                "CREATE INDEX IF NOT EXISTS ix_customization_options_field_name ON customization_options (field_name)",
                "ALTER TABLE customization_options ALTER COLUMN id SET DEFAULT gen_random_uuid()",
                "ALTER TABLE customization_options ALTER COLUMN sort_order SET DEFAULT 0",
                "ALTER TABLE customization_options ALTER COLUMN is_active SET DEFAULT TRUE",
                "ALTER TABLE customization_options ALTER COLUMN is_deleted SET DEFAULT FALSE",
                "ALTER TABLE customization_options ALTER COLUMN created_at SET DEFAULT NOW()",
                "ALTER TABLE customization_options ALTER COLUMN updated_at SET DEFAULT NOW()",
                """
                -- Fresh-install seed only: default option set is inserted just once, when the
                -- table is empty. On existing (multi-tenant) databases the rows already exist and
                -- carry a company_id, so this is skipped — avoiding NULL-company_id duplicates and
                -- removing the dependency on the old global unique (module, field_name, option_value).
                DO $$
                BEGIN
                IF NOT EXISTS (SELECT 1 FROM customization_options) THEN
                INSERT INTO customization_options (module, field_name, option_value, display_label, sort_order, is_active)
                VALUES
                    ('customer', 'currency', 'INR', 'INR', 1, TRUE),
                    ('customer', 'currency', 'USD', 'USD', 2, TRUE),
                    ('customer', 'currency', 'EUR', 'EUR', 3, TRUE),
                    ('customer', 'currency', 'GBP', 'GBP', 4, TRUE),
                    ('customer', 'country', 'India', 'India', 1, TRUE),
                    ('customer', 'country', 'United States', 'United States', 2, TRUE),
                    ('customer', 'country', 'United Arab Emirates', 'United Arab Emirates', 3, TRUE),
                    ('customer', 'country', 'United Kingdom', 'United Kingdom', 4, TRUE),
                    ('customer', 'country', 'Singapore', 'Singapore', 5, TRUE),
                    ('customer', 'country', 'Australia', 'Australia', 6, TRUE),
                    ('customer', 'state', 'Andhra Pradesh', 'Andhra Pradesh', 1, TRUE),
                    ('customer', 'state', 'Arunachal Pradesh', 'Arunachal Pradesh', 2, TRUE),
                    ('customer', 'state', 'Assam', 'Assam', 3, TRUE),
                    ('customer', 'state', 'Bihar', 'Bihar', 4, TRUE),
                    ('customer', 'state', 'Chhattisgarh', 'Chhattisgarh', 5, TRUE),
                    ('customer', 'state', 'Goa', 'Goa', 6, TRUE),
                    ('customer', 'state', 'Gujarat', 'Gujarat', 7, TRUE),
                    ('customer', 'state', 'Haryana', 'Haryana', 8, TRUE),
                    ('customer', 'state', 'Himachal Pradesh', 'Himachal Pradesh', 9, TRUE),
                    ('customer', 'state', 'Jharkhand', 'Jharkhand', 10, TRUE),
                    ('customer', 'state', 'Karnataka', 'Karnataka', 11, TRUE),
                    ('customer', 'state', 'Kerala', 'Kerala', 12, TRUE),
                    ('customer', 'state', 'Madhya Pradesh', 'Madhya Pradesh', 13, TRUE),
                    ('customer', 'state', 'Maharashtra', 'Maharashtra', 14, TRUE),
                    ('customer', 'state', 'Manipur', 'Manipur', 15, TRUE),
                    ('customer', 'state', 'Meghalaya', 'Meghalaya', 16, TRUE),
                    ('customer', 'state', 'Mizoram', 'Mizoram', 17, TRUE),
                    ('customer', 'state', 'Nagaland', 'Nagaland', 18, TRUE),
                    ('customer', 'state', 'Odisha', 'Odisha', 19, TRUE),
                    ('customer', 'state', 'Punjab', 'Punjab', 20, TRUE),
                    ('customer', 'state', 'Rajasthan', 'Rajasthan', 21, TRUE),
                    ('customer', 'state', 'Sikkim', 'Sikkim', 22, TRUE),
                    ('customer', 'state', 'Tamil Nadu', 'Tamil Nadu', 23, TRUE),
                    ('customer', 'state', 'Telangana', 'Telangana', 24, TRUE),
                    ('customer', 'state', 'Tripura', 'Tripura', 25, TRUE),
                    ('customer', 'state', 'Uttar Pradesh', 'Uttar Pradesh', 26, TRUE),
                    ('customer', 'state', 'Uttarakhand', 'Uttarakhand', 27, TRUE),
                    ('customer', 'state', 'West Bengal', 'West Bengal', 28, TRUE),
                    ('customer', 'state', 'Delhi', 'Delhi', 29, TRUE),
                    ('rdn', 'return_reason', 'wrong_supply', 'Wrong Supply', 1, TRUE),
                    ('rdn', 'return_reason', 'expiry_date_passed', 'Expiry Date Passed', 2, TRUE),
                    ('rdn', 'return_reason', 'non_sold', 'Non Sold', 3, TRUE),
                    ('rdn', 'return_reason', 'damaged', 'Damaged', 4, TRUE);
                END IF;
                END $$
                """,

            # GST report audit trail persistence
            """
            CREATE TABLE IF NOT EXISTS gst_report_audit_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id),
                action VARCHAR(120) NOT NULL,
                report_type VARCHAR(40) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                frequency VARCHAR(20) NOT NULL,
                \"timestamp\" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                status VARCHAR(20) NOT NULL,
                details JSONB NOT NULL DEFAULT '{}'::jsonb,
                company_id UUID
            )
            """,
            # Multi-tenant: ensure company_id exists on pre-existing installs too
            # (CREATE TABLE IF NOT EXISTS won't add it to an already-created table).
            # Must run BEFORE the residual backfill below, which UPDATEs this column.
            "ALTER TABLE gst_report_audit_logs ADD COLUMN IF NOT EXISTS company_id UUID",
            "CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_timestamp ON gst_report_audit_logs (\"timestamp\")",
            "CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_report_type ON gst_report_audit_logs (report_type)",
            "CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_user_id ON gst_report_audit_logs (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_company_id ON gst_report_audit_logs (company_id)",

            # Customer international phone support
            "ALTER TABLE customers ALTER COLUMN phone TYPE VARCHAR(20)",
            "ALTER TABLE customers ALTER COLUMN alternate_phone TYPE VARCHAR(20)",

            # Sensitive-field encryption storage compatibility
            "ALTER TABLE customers ALTER COLUMN pan TYPE VARCHAR(255)",
            "ALTER TABLE suppliers ALTER COLUMN pan TYPE VARCHAR(255)",
            "ALTER TABLE suppliers ALTER COLUMN bank_account_no TYPE VARCHAR(255)",

            # Action logs with query/filter support
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id),
                username VARCHAR(255),
                action VARCHAR(120) NOT NULL,
                action_type VARCHAR(40) NOT NULL DEFAULT 'UNKNOWN',
                module_name VARCHAR(80) NOT NULL DEFAULT 'system',
                resource_type VARCHAR(80),
                resource_id UUID,
                record_reference VARCHAR(255),
                description TEXT,
                status VARCHAR(20) NOT NULL,
                details JSONB NOT NULL DEFAULT '{}'::jsonb,
                ip_address VARCHAR(64),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS username VARCHAR(255)",
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS action_type VARCHAR(40)",
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS module_name VARCHAR(80)",
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS record_reference VARCHAR(255)",
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_module_name ON audit_logs (module_name)",
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_action_type ON audit_logs (action_type)",
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_record_reference ON audit_logs (record_reference)",

            # MCN-FEAT-PROFORMA: Proforma Invoice module (separate PFI numbering + tables)
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS pfi_prefix VARCHAR(10) NOT NULL DEFAULT 'PFI'",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS pfi_counter INTEGER NOT NULL DEFAULT 1",
            """
            CREATE TABLE IF NOT EXISTS proforma_invoices (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                proforma_number VARCHAR(30) UNIQUE NOT NULL,
                customer_id UUID NOT NULL REFERENCES customers(id),
                proforma_date DATE NOT NULL,
                valid_until DATE,
                status VARCHAR(20) NOT NULL DEFAULT 'draft',
                sold_to_customer_id UUID REFERENCES customers(id),
                bill_to_customer_id UUID NOT NULL REFERENCES customers(id),
                ship_to_customer_id UUID REFERENCES customers(id),
                subtotal INTEGER NOT NULL DEFAULT 0,
                total_discount INTEGER NOT NULL DEFAULT 0,
                total_taxable_amount INTEGER NOT NULL DEFAULT 0,
                total_cgst INTEGER NOT NULL DEFAULT 0,
                total_sgst INTEGER NOT NULL DEFAULT 0,
                total_igst INTEGER NOT NULL DEFAULT 0,
                total_gst INTEGER NOT NULL DEFAULT 0,
                total_amount INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                terms_conditions TEXT,
                is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                deleted_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                company_id UUID REFERENCES company(id),
                created_by UUID REFERENCES users(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS proforma_invoice_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                proforma_invoice_id UUID NOT NULL REFERENCES proforma_invoices(id) ON DELETE CASCADE,
                product_id UUID NOT NULL REFERENCES products(id),
                description VARCHAR(255),
                quantity NUMERIC(12,4) NOT NULL,
                unit_price INTEGER NOT NULL,
                discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
                discount_amount INTEGER NOT NULL DEFAULT 0,
                taxable_amount INTEGER NOT NULL,
                gst_rate INTEGER NOT NULL,
                cgst_amount INTEGER NOT NULL DEFAULT 0,
                sgst_amount INTEGER NOT NULL DEFAULT 0,
                igst_amount INTEGER NOT NULL DEFAULT 0,
                total_amount INTEGER NOT NULL,
                is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                deleted_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_proforma_invoices_number ON proforma_invoices (proforma_number)",
            "CREATE INDEX IF NOT EXISTS ix_proforma_invoices_customer_id ON proforma_invoices (customer_id)",
            "CREATE INDEX IF NOT EXISTS ix_proforma_invoices_company_id ON proforma_invoices (company_id)",
            "CREATE INDEX IF NOT EXISTS ix_proforma_invoice_items_proforma_id ON proforma_invoice_items (proforma_invoice_id)",
            "CREATE INDEX IF NOT EXISTS ix_proforma_invoice_items_product_id ON proforma_invoice_items (product_id)",

            # --- Multi-tenant company_id sync for ALL scoped tables ---
            # Earlier this runner only added company_id to users/products/customers/suppliers,
            # but the models scope many more tables (purchase, sales, payments, stock, counts).
            # Add the column + index idempotently everywhere so query filters on company_id
            # never raise "column does not exist". Runs after all CREATE TABLE statements above
            # so every target table is guaranteed to exist.
            *[
                stmt
                for _table in (
                    "purchase_orders", "goods_receipt_notes", "purchase_returns",
                    "quotations", "sales_orders", "sales_invoices", "sales_returns",
                    "payments", "stock_ledger", "inventory_counts",
                    "inventory_count_difference_audits", "return_delivery_notes",
                    "rdn_credit_notes", "proforma_invoices",
                )
                for stmt in (
                    f"ALTER TABLE {_table} ADD COLUMN IF NOT EXISTS company_id UUID",
                    f"CREATE INDEX IF NOT EXISTS ix_{_table}_company_id ON {_table} (company_id)",
                )
            ],
            # Backfill existing rows to the single company so historical records stay visible
            # under company_id scoping (NULL company_id would not match any scoped query).
            """
            DO $$
            DECLARE company_uuid UUID;
            BEGIN
                SELECT id INTO company_uuid FROM company ORDER BY created_at ASC LIMIT 1;
                IF company_uuid IS NOT NULL THEN
                    UPDATE purchase_orders SET company_id = company_uuid WHERE company_id IS NULL;
                    UPDATE goods_receipt_notes SET company_id = company_uuid WHERE company_id IS NULL;
                    UPDATE purchase_returns SET company_id = company_uuid WHERE company_id IS NULL;
                    UPDATE quotations SET company_id = company_uuid WHERE company_id IS NULL;
                    UPDATE sales_orders SET company_id = company_uuid WHERE company_id IS NULL;
                    UPDATE sales_invoices SET company_id = company_uuid WHERE company_id IS NULL;
                    UPDATE sales_returns SET company_id = company_uuid WHERE company_id IS NULL;
                    UPDATE payments SET company_id = company_uuid WHERE company_id IS NULL;
                    UPDATE stock_ledger SET company_id = company_uuid WHERE company_id IS NULL;
                    UPDATE inventory_counts SET company_id = company_uuid WHERE company_id IS NULL;
                    UPDATE inventory_count_difference_audits SET company_id = company_uuid WHERE company_id IS NULL;
                    UPDATE return_delivery_notes SET company_id = company_uuid WHERE company_id IS NULL;
                    UPDATE rdn_credit_notes SET company_id = company_uuid WHERE company_id IS NULL;
                    UPDATE proforma_invoices SET company_id = company_uuid WHERE company_id IS NULL;
                END IF;
            END $$
            """,

            # ── Multi-tenant M0 (DB-206): promote `company` to a tenant registry.
            #    Additive subscription / lifecycle columns; legacy tenant defaults
            #    to an ACTIVE, PLATINUM, paid account so nothing is gated/locked.
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(20) NOT NULL DEFAULT 'PLATINUM'",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS account_status VARCHAR(20) NOT NULL DEFAULT 'active'",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) NOT NULL DEFAULT 'paid'",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS onboarding_date DATE DEFAULT CURRENT_DATE",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS subscription_start_date DATE",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS subscription_expiry_date DATE",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS business_category VARCHAR(100)",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS contact_person_name VARCHAR(255)",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS contact_number VARCHAR(20)",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS tenant_code VARCHAR(50)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_company_tenant_code ON company (tenant_code) WHERE tenant_code IS NOT NULL",
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'company_subscription_plan_check') THEN
                    ALTER TABLE company ADD CONSTRAINT company_subscription_plan_check
                        CHECK (subscription_plan IN ('FREE','SILVER','GOLD','PLATINUM'));
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'company_account_status_check') THEN
                    ALTER TABLE company ADD CONSTRAINT company_account_status_check
                        CHECK (account_status IN ('active','inactive','suspended','trial'));
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'company_payment_status_check') THEN
                    ALTER TABLE company ADD CONSTRAINT company_payment_status_check
                        CHECK (payment_status IN ('paid','pending','overdue'));
                END IF;
            END $$
            """,
            "UPDATE company SET onboarding_date = COALESCE(onboarding_date, created_at::date, CURRENT_DATE) WHERE onboarding_date IS NULL",

            # ── Residual company_id backfill (DB-213): tables the earlier backfills
            #    missed. product_categories = tenant data → legacy tenant; audit
            #    tables = derive from acting user (system/pre-auth rows stay NULL).
            "ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS company_id UUID",
            "CREATE INDEX IF NOT EXISTS ix_product_categories_company_id ON product_categories (company_id)",
            # Guarantee company_id exists on both audit tables before backfilling them
            # (idempotent; audit_logs.company_id is normally added by the v1.5 block,
            # but add it here too so the backfill can never hit an undefined column).
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS company_id UUID",
            "ALTER TABLE gst_report_audit_logs ADD COLUMN IF NOT EXISTS company_id UUID",
            """
            DO $$
            DECLARE _legacy UUID;
            BEGIN
                SELECT id INTO _legacy FROM company ORDER BY created_at ASC LIMIT 1;
                IF _legacy IS NULL THEN RETURN; END IF;
                UPDATE product_categories SET company_id = _legacy WHERE company_id IS NULL;
                UPDATE audit_logs a SET company_id = u.company_id
                    FROM users u WHERE a.user_id = u.id
                      AND a.company_id IS NULL AND u.company_id IS NOT NULL;
                UPDATE gst_report_audit_logs g SET company_id = u.company_id
                    FROM users u WHERE g.user_id = u.id
                      AND g.company_id IS NULL AND u.company_id IS NOT NULL;
            END $$
            """,
            # product_categories.name: global unique -> per-tenant unique (DB-213).
            """
            DO $$
            DECLARE con_name TEXT; idx_name TEXT;
            BEGIN
                FOR con_name IN
                    SELECT tc.constraint_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                    WHERE tc.table_schema = current_schema()
                      AND tc.table_name = 'product_categories'
                      AND tc.constraint_type = 'UNIQUE'
                    GROUP BY tc.constraint_name
                    HAVING COUNT(*) = 1 AND MAX(kcu.column_name) = 'name'
                LOOP
                    EXECUTE format('ALTER TABLE product_categories DROP CONSTRAINT %I', con_name);
                END LOOP;
                FOR idx_name IN
                    SELECT i.relname FROM pg_index x
                    JOIN pg_class i ON i.oid = x.indexrelid
                    JOIN pg_class t ON t.oid = x.indrelid
                    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(x.indkey)
                    WHERE t.relname = 'product_categories' AND x.indisunique = TRUE
                      AND x.indnatts = 1 AND a.attname = 'name' AND NOT x.indisprimary
                LOOP
                    EXECUTE format('DROP INDEX IF EXISTS %I', idx_name);
                END LOOP;
                CREATE UNIQUE INDEX IF NOT EXISTS ux_product_categories_company_name
                    ON product_categories (company_id, name);
            END $$
            """,

            # ── BRD role model (DB-218): rename legacy roles to their BRD names and
            #    tighten users.role to the Tenant Admin + the 5 BRD end-user roles.
            #    General Manager → Accounts, Inventory Manager → Inventory.
            "UPDATE users SET role = 'accounts' WHERE role = 'general manager'",
            "UPDATE users SET role = 'inventory' WHERE role = 'inventory manager'",
            "ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check",
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM users
                    WHERE role NOT IN ('admin','basic','accounts','inventory','management','hr')
                ) THEN
                    ALTER TABLE users ADD CONSTRAINT users_role_check
                        CHECK (role IN ('admin','basic','accounts','inventory','management','hr'));
                ELSE
                    -- Stragglers exist; keep the legacy-inclusive check so nothing breaks.
                    ALTER TABLE users ADD CONSTRAINT users_role_check
                        CHECK (role IN ('admin','inventory manager','general manager',
                                        'basic','accounts','inventory','management','hr'));
                    RAISE NOTICE 'users_role_check: legacy-inclusive (un-migrated role values exist)';
                END IF;
            END $$
            """,

            # ── Multi-tenant M4 (DB-210): platform Super Admin flag.
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN NOT NULL DEFAULT FALSE",
            "CREATE INDEX IF NOT EXISTS ix_users_is_super_admin ON users (is_super_admin) WHERE is_super_admin = TRUE",

            # ── Multi-tenant M5 (DB-211): Service Invoice module.
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS svc_prefix VARCHAR(10) NOT NULL DEFAULT 'SINV'",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS svc_counter INTEGER NOT NULL DEFAULT 1",
            """
            CREATE TABLE IF NOT EXISTS service_invoices (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                invoice_number VARCHAR(40) NOT NULL,
                invoice_date DATE NOT NULL,
                due_date DATE,
                customer_name VARCHAR(255) NOT NULL,
                customer_gstin VARCHAR(15),
                customer_email VARCHAR(255),
                customer_contact VARCHAR(20),
                billing_address TEXT,
                customer_state_code VARCHAR(5),
                supply_type VARCHAR(10) NOT NULL DEFAULT 'intra',
                subtotal INTEGER NOT NULL DEFAULT 0,
                total_discount INTEGER NOT NULL DEFAULT 0,
                total_taxable_amount INTEGER NOT NULL DEFAULT 0,
                total_cgst INTEGER NOT NULL DEFAULT 0,
                total_sgst INTEGER NOT NULL DEFAULT 0,
                total_igst INTEGER NOT NULL DEFAULT 0,
                total_gst INTEGER NOT NULL DEFAULT 0,
                grand_total INTEGER NOT NULL DEFAULT 0,
                amount_in_words VARCHAR(500),
                status VARCHAR(20) NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','issued','paid','cancelled')),
                payment_status VARCHAR(20) NOT NULL DEFAULT 'unpaid'
                    CHECK (payment_status IN ('unpaid','paid')),
                cancel_reason TEXT,
                notes TEXT,
                is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                deleted_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                company_id UUID REFERENCES company(id),
                created_by UUID REFERENCES users(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS service_invoice_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                service_invoice_id UUID NOT NULL REFERENCES service_invoices(id) ON DELETE CASCADE,
                sr_no INTEGER NOT NULL DEFAULT 1,
                item_name VARCHAR(255) NOT NULL,
                description TEXT,
                hsn_sac_code VARCHAR(20),
                quantity NUMERIC(12,4) NOT NULL DEFAULT 1,
                basic_price INTEGER NOT NULL DEFAULT 0,
                discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
                discount_amount INTEGER NOT NULL DEFAULT 0,
                is_free BOOLEAN NOT NULL DEFAULT FALSE,
                taxable_amount INTEGER NOT NULL DEFAULT 0,
                gst_rate INTEGER NOT NULL DEFAULT 18,
                cgst_amount INTEGER NOT NULL DEFAULT 0,
                sgst_amount INTEGER NOT NULL DEFAULT 0,
                igst_amount INTEGER NOT NULL DEFAULT 0,
                total_amount INTEGER NOT NULL DEFAULT 0,
                is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_service_invoices_company_id ON service_invoices (company_id)",
            "CREATE INDEX IF NOT EXISTS ix_service_invoices_invoice_date ON service_invoices (invoice_date)",
            "CREATE INDEX IF NOT EXISTS ix_service_invoice_items_invoice_id ON service_invoice_items (service_invoice_id)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_service_invoices_company_number ON service_invoices (company_id, invoice_number)",
            # Platform (Super Admin → tenant) subscription invoices (DB-217).
            "ALTER TABLE service_invoices ADD COLUMN IF NOT EXISTS is_platform_invoice BOOLEAN NOT NULL DEFAULT FALSE",
            "CREATE INDEX IF NOT EXISTS ix_service_invoices_is_platform ON service_invoices (is_platform_invoice) WHERE is_platform_invoice = TRUE",

            # Platform (Mecandria) seller company profile (DB-219).
            """
            CREATE TABLE IF NOT EXISTS platform_company (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL DEFAULT 'Mecandria',
                legal_name VARCHAR(255),
                gstin VARCHAR(15),
                gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered',
                pan VARCHAR(10),
                import_export_number VARCHAR(50),
                company_director_name VARCHAR(255),
                company_director_contact VARCHAR(255),
                address_line1 VARCHAR(255),
                address_line2 VARCHAR(255),
                city VARCHAR(100),
                state VARCHAR(100),
                country VARCHAR(100),
                state_code VARCHAR(5),
                pincode VARCHAR(10),
                phone VARCHAR(15),
                email VARCHAR(255),
                website VARCHAR(255),
                logo_url VARCHAR(500),
                ambassador_logo_url VARCHAR(500),
                bank_name VARCHAR(150),
                account_holder_name VARCHAR(255),
                bank_account_no VARCHAR(50),
                bank_ifsc VARCHAR(20),
                bank_branch VARCHAR(150),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            INSERT INTO platform_company (name)
            SELECT 'Mecandria'
            WHERE NOT EXISTS (SELECT 1 FROM platform_company)
            """,

            # ── Multi-tenant M1 (DB-207): per-tenant document numbering.
            #    Convert each global UNIQUE(number) into composite UNIQUE(company_id,
            #    number) so numbers are unique within a tenant but may repeat across
            #    tenants. Dynamic + idempotent; equivalent to the old constraint while
            #    a single tenant exists.
            """
            DO $$
            DECLARE
                r RECORD;
                con_name TEXT;
                idx_name TEXT;
            BEGIN
                FOR r IN
                    SELECT * FROM (VALUES
                        ('purchase_orders',       'po_number'),
                        ('goods_receipt_notes',   'grn_number'),
                        ('purchase_returns',      'return_number'),
                        ('quotations',            'quotation_number'),
                        ('proforma_invoices',     'proforma_number'),
                        ('sales_orders',          'so_number'),
                        ('sales_invoices',        'invoice_number'),
                        ('sales_returns',         'return_number'),
                        ('return_delivery_notes', 'rdn_number'),
                        ('rdn_credit_notes',      'credit_note_number'),
                        ('payments',              'payment_number'),
                        ('inventory_counts',      'count_number')
                    ) AS t(tbl, col)
                LOOP
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name = r.tbl AND column_name = 'company_id'
                    ) THEN
                        CONTINUE;
                    END IF;
                    FOR con_name IN
                        SELECT tc.constraint_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                          ON tc.constraint_name = kcu.constraint_name
                         AND tc.table_schema = kcu.table_schema
                        WHERE tc.table_schema = current_schema()
                          AND tc.table_name = r.tbl
                          AND tc.constraint_type = 'UNIQUE'
                        GROUP BY tc.constraint_name
                        HAVING COUNT(*) = 1 AND MAX(kcu.column_name) = r.col
                    LOOP
                        EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', r.tbl, con_name);
                    END LOOP;
                    FOR idx_name IN
                        SELECT i.relname
                        FROM pg_index x
                        JOIN pg_class i ON i.oid = x.indexrelid
                        JOIN pg_class t ON t.oid = x.indrelid
                        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(x.indkey)
                        WHERE t.relname = r.tbl
                          AND x.indisunique = TRUE
                          AND x.indnatts = 1
                          AND a.attname = r.col
                          AND NOT x.indisprimary
                    LOOP
                        EXECUTE format('DROP INDEX IF EXISTS %I', idx_name);
                    END LOOP;
                    EXECUTE format(
                        'CREATE UNIQUE INDEX IF NOT EXISTS ux_%s_company_number ON %I (company_id, %I)',
                        r.tbl, r.tbl, r.col
                    );
                END LOOP;
            END $$
            """,

            # ── Multi-tenant M7 (DB-212): defence-in-depth NOT NULL on company_id.
            #    Guarded: only set NOT NULL where the table has zero NULL company_id
            #    (so it never fails). Runs last, after every table + backfill above.
            #    NOTE: `users` is intentionally EXCLUDED — platform Super Admins are
            #    tenant-less (company_id IS NULL). Users are protected by a guarded
            #    CHECK below instead (DB-214) so super admins remain insertable.
            """
            DO $$
            DECLARE
                t TEXT;
                null_count BIGINT;
                tables TEXT[] := ARRAY[
                    'products', 'customers', 'suppliers',
                    'stockists', 'sales_managers',
                    'purchase_orders', 'goods_receipt_notes', 'purchase_returns',
                    'quotations', 'sales_orders', 'sales_invoices', 'sales_returns',
                    'proforma_invoices', 'return_delivery_notes', 'rdn_credit_notes',
                    'payments', 'stock_ledger', 'service_invoices'
                ];
            BEGIN
                FOREACH t IN ARRAY tables LOOP
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name = t AND column_name = 'company_id'
                    ) THEN
                        CONTINUE;
                    END IF;
                    EXECUTE format('SELECT COUNT(*) FROM %I WHERE company_id IS NULL', t)
                        INTO null_count;
                    IF null_count = 0 THEN
                        EXECUTE format('ALTER TABLE %I ALTER COLUMN company_id SET NOT NULL', t);
                    END IF;
                END LOOP;
            END $$
            """,

            # ── Multi-tenant M7 fix (DB-214): users.company_id must stay NULLable so
            #    platform Super Admins (no tenant) can exist. An earlier M7 run may
            #    have set it NOT NULL — drop that, then enforce tenant membership via
            #    a guarded CHECK (every user has a company OR is a super admin).
            "ALTER TABLE users ALTER COLUMN company_id DROP NOT NULL",
            """
            DO $$
            BEGIN
                ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_company_or_super;
                -- Only add the constraint if no existing row violates it.
                IF NOT EXISTS (
                    SELECT 1 FROM users
                    WHERE company_id IS NULL AND is_super_admin = FALSE
                ) THEN
                    ALTER TABLE users ADD CONSTRAINT chk_users_company_or_super
                        CHECK (company_id IS NOT NULL OR is_super_admin = TRUE);
                ELSE
                    RAISE NOTICE 'M7 fix: SKIP chk_users_company_or_super — tenant-less non-super-admin user(s) exist';
                END IF;
            END $$
            """,

            # ── Multi-tenant customization_options scoping (DB-215): the dropdown
            #    option table had NO company_id and was shared by every tenant
            #    (cross-tenant leak). Add company_id + FK + index, backfill to the
            #    legacy tenant, and replace the GLOBAL unique with a per-tenant one.
            "ALTER TABLE customization_options ADD COLUMN IF NOT EXISTS company_id UUID",
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_customization_options_company') THEN
                    ALTER TABLE customization_options
                        ADD CONSTRAINT fk_customization_options_company
                        FOREIGN KEY (company_id) REFERENCES company(id);
                END IF;
            END $$
            """,
            "CREATE INDEX IF NOT EXISTS ix_customization_options_company_id ON customization_options (company_id)",
            """
            DO $$
            DECLARE _legacy_company_id UUID;
            BEGIN
                SELECT id INTO _legacy_company_id FROM company ORDER BY created_at ASC LIMIT 1;
                IF _legacy_company_id IS NOT NULL THEN
                    UPDATE customization_options
                    SET company_id = _legacy_company_id
                    WHERE company_id IS NULL;
                END IF;
            END $$
            """,
            "ALTER TABLE customization_options DROP CONSTRAINT IF EXISTS uq_customization_option_scope",
            # The old global unique may exist as a standalone INDEX (not a constraint),
            # which DROP CONSTRAINT does not remove — drop the index form too, else it
            # keeps enforcing cross-tenant uniqueness on (module, field_name, option_value).
            "DROP INDEX IF EXISTS uq_customization_option_scope",
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_customization_options_company_scope
                ON customization_options (company_id, module, field_name, option_value)
            """,

            # ── Per-tenant master codes (DB-220): convert the GLOBAL unique on
            #    customer_code/supplier_code/product_code into a PER-TENANT composite
            #    unique (company_id, <code>) so a new tenant's first code never
            #    collides with another tenant's identical code.
            """
            DO $$
            DECLARE
                spec RECORD; con_name TEXT; idx_name TEXT;
            BEGIN
                FOR spec IN
                    SELECT * FROM (VALUES
                        ('customers', 'customer_code', 'ux_customers_company_code'),
                        ('suppliers', 'supplier_code', 'ux_suppliers_company_code'),
                        ('products',  'product_code',  'ux_products_company_code')
                    ) AS t(tbl, col, newidx)
                LOOP
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name = spec.tbl AND column_name = 'company_id'
                    ) THEN
                        CONTINUE;
                    END IF;
                    FOR con_name IN
                        SELECT tc.constraint_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                        WHERE tc.table_schema = current_schema()
                          AND tc.table_name = spec.tbl AND tc.constraint_type = 'UNIQUE'
                        GROUP BY tc.constraint_name
                        HAVING COUNT(*) = 1 AND MAX(kcu.column_name) = spec.col
                    LOOP
                        EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', spec.tbl, con_name);
                    END LOOP;
                    FOR idx_name IN
                        SELECT i.relname FROM pg_index x
                        JOIN pg_class i ON i.oid = x.indexrelid
                        JOIN pg_class t ON t.oid = x.indrelid
                        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(x.indkey)
                        WHERE t.relname = spec.tbl AND x.indisunique = TRUE
                          AND x.indnatts = 1 AND a.attname = spec.col AND NOT x.indisprimary
                    LOOP
                        EXECUTE format('DROP INDEX IF EXISTS %I', idx_name);
                    END LOOP;
                    EXECUTE format(
                        'CREATE UNIQUE INDEX IF NOT EXISTS %I ON %I (company_id, %I)',
                        spec.newidx, spec.tbl, spec.col
                    );
                END LOOP;
            END $$
            """,

            # ── Users email: partial unique so deleted users don't block re-use of
            #    their email, while active emails stay globally unique (DB-221).
            """
            DO $$
            DECLARE con TEXT;
            BEGIN
                FOR con IN
                    SELECT tc.constraint_name FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                    WHERE tc.table_schema = current_schema()
                      AND tc.table_name = 'users' AND tc.constraint_type = 'UNIQUE'
                    GROUP BY tc.constraint_name
                    HAVING COUNT(*) = 1 AND MAX(kcu.column_name) = 'email'
                LOOP
                    EXECUTE format('ALTER TABLE users DROP CONSTRAINT %I', con);
                END LOOP;
            END $$
            """,
            "DROP INDEX IF EXISTS users_email_key",
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_active ON users (email) WHERE is_deleted = false",

            # ── Subscription Plan Configuration (DB-222): DB-backed plan matrix so
            #    the Super Admin can configure pricing/modules/features/limits/status
            #    per plan. plan_service reads these rows (cached) with a code fallback.
            """
            CREATE TABLE IF NOT EXISTS subscription_plans (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                plan_key VARCHAR(20) NOT NULL UNIQUE,
                name VARCHAR(80) NOT NULL,
                price_paise BIGINT NOT NULL DEFAULT 0,
                billing_period VARCHAR(20) NOT NULL DEFAULT 'monthly',
                user_limit INTEGER NOT NULL DEFAULT 1,
                modules JSONB NOT NULL DEFAULT '[]'::jsonb,
                features JSONB NOT NULL DEFAULT '[]'::jsonb,
                roles JSONB NOT NULL DEFAULT '[]'::jsonb,
                free_invoice_cap INTEGER,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_subscription_plans_plan_key ON subscription_plans (plan_key)",
            """
            INSERT INTO subscription_plans
                (plan_key, name, price_paise, billing_period, user_limit, modules, features, roles, free_invoice_cap, is_active, sort_order)
            VALUES
                ('FREE', 'Free', 0, 'none', 1,
                 '["service_invoice"]'::jsonb,
                 '["email_invoices"]'::jsonb,
                 '["basic"]'::jsonb,
                 10, TRUE, 1),
                ('SILVER', 'Silver', 99900, 'monthly', 2,
                 '["service_invoice","masters","purchase","sales","accounts","dashboard"]'::jsonb,
                 '["email_invoices"]'::jsonb,
                 '["admin","accounts"]'::jsonb,
                 NULL, TRUE, 2),
                ('GOLD', 'Gold', 199900, 'monthly', 4,
                 '["service_invoice","masters","purchase","sales","accounts","dashboard","inventory","reports","audit_logs"]'::jsonb,
                 '["email_invoices","advanced_reports","gst_filing","audit_trail"]'::jsonb,
                 '["admin","accounts","inventory","management"]'::jsonb,
                 NULL, TRUE, 3),
                ('PLATINUM', 'Platinum', 499900, 'monthly', 6,
                 '["service_invoice","masters","purchase","sales","accounts","dashboard","inventory","reports","audit_logs","export","pos","hr"]'::jsonb,
                 '["email_invoices","advanced_reports","gst_filing","data_export","bulk_import","multi_currency","audit_trail","api_access"]'::jsonb,
                 '["admin","accounts","inventory","management","hr"]'::jsonb,
                 NULL, TRUE, 4)
            ON CONFLICT (plan_key) DO NOTHING
            """,

            # BE-261: settle invoices from CLEARED receipts only. Re-derive every
            # invoice's amount_paid/amount_due/status from its cleared allocations
            # (pending receipts reserve capacity but no longer settle). Idempotent.
            """
            UPDATE sales_invoices si
            SET amount_paid = sub.paid,
                amount_due  = si.total_amount - sub.paid,
                status = CASE
                    WHEN lower(trim(si.status)) NOT IN ('issued','partial_paid','paid') THEN si.status
                    WHEN si.total_amount > 0 AND si.total_amount - sub.paid = 0 THEN 'paid'
                    WHEN sub.paid > 0 THEN 'partial_paid'
                    ELSE 'issued'
                END
            FROM (
                SELECT si2.id,
                       LEAST(si2.total_amount, COALESCE((
                           SELECT SUM(pa.allocated_amount)
                           FROM payment_allocations pa
                           JOIN payments p ON p.id = pa.payment_id
                           WHERE pa.invoice_id = si2.id
                             AND pa.is_deleted = false
                             AND p.is_deleted = false
                             AND lower(trim(p.status)) IN ('cleared','advance_payment_cleared','advance_cleared','full_payment_cleared')
                       ), 0)) AS paid
                FROM sales_invoices si2
                WHERE si2.is_deleted = false
            ) sub
            WHERE si.id = sub.id AND si.is_deleted = false
            """,
    ]

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))

    print("Compatibility migration successful.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
