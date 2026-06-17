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
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_customization_option_scope ON customization_options (module, field_name, option_value)",
                "CREATE INDEX IF NOT EXISTS ix_customization_options_module ON customization_options (module)",
                "CREATE INDEX IF NOT EXISTS ix_customization_options_field_name ON customization_options (field_name)",
                "ALTER TABLE customization_options ALTER COLUMN id SET DEFAULT gen_random_uuid()",
                "ALTER TABLE customization_options ALTER COLUMN sort_order SET DEFAULT 0",
                "ALTER TABLE customization_options ALTER COLUMN is_active SET DEFAULT TRUE",
                "ALTER TABLE customization_options ALTER COLUMN is_deleted SET DEFAULT FALSE",
                "ALTER TABLE customization_options ALTER COLUMN created_at SET DEFAULT NOW()",
                "ALTER TABLE customization_options ALTER COLUMN updated_at SET DEFAULT NOW()",
                """
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
                    ('rdn', 'return_reason', 'damaged', 'Damaged', 4, TRUE)
                ON CONFLICT (module, field_name, option_value) DO NOTHING
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
                details JSONB NOT NULL DEFAULT '{}'::jsonb
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_timestamp ON gst_report_audit_logs (\"timestamp\")",
            "CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_report_type ON gst_report_audit_logs (report_type)",
            "CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_user_id ON gst_report_audit_logs (user_id)",

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
    ]

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))

    print("Compatibility migration successful.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
