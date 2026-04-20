-- IMS Reference Queries (DO NOT run automatically)
-- Useful for manual verification and debugging.

-- List all tables
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- Count key tables
SELECT 'users' AS tbl, COUNT(*) FROM users
UNION ALL SELECT 'company', COUNT(*) FROM company
UNION ALL SELECT 'customers', COUNT(*) FROM customers
UNION ALL SELECT 'suppliers', COUNT(*) FROM suppliers
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'units_of_measure', COUNT(*) FROM units_of_measure
UNION ALL SELECT 'product_categories', COUNT(*) FROM product_categories
UNION ALL SELECT 'purchase_orders', COUNT(*) FROM purchase_orders
UNION ALL SELECT 'purchase_order_items', COUNT(*) FROM purchase_order_items
UNION ALL SELECT 'goods_receipt_notes', COUNT(*) FROM goods_receipt_notes
UNION ALL SELECT 'grn_items', COUNT(*) FROM grn_items
UNION ALL SELECT 'quotations', COUNT(*) FROM quotations
UNION ALL SELECT 'sales_orders', COUNT(*) FROM sales_orders
UNION ALL SELECT 'sales_invoices', COUNT(*) FROM sales_invoices
UNION ALL SELECT 'payments', COUNT(*) FROM payments
UNION ALL SELECT 'stock_ledger', COUNT(*) FROM stock_ledger
ORDER BY tbl;

-- Verify at least one active admin exists
SELECT id, email, role, is_active, force_password_change
FROM users
WHERE role = 'admin' AND is_active = TRUE;

-- Verify critical columns introduced via compatibility migrations
SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema = 'public'
	AND (
		(table_name = 'purchase_orders' AND column_name IN ('currency_code', 'exchange_rate', 'is_deleted', 'deleted_at'))
		OR (table_name = 'sales_orders' AND column_name IN ('currency_code', 'exchange_rate', 'is_deleted', 'deleted_at'))
		OR (table_name = 'grn_items' AND column_name IN ('batch_no', 'manufacture_date', 'expiry_date'))
		OR (table_name = 'payments' AND column_name IN ('is_deleted', 'deleted_at'))
		OR (table_name = 'sales_invoices' AND column_name IN ('is_deleted', 'deleted_at'))
	)
ORDER BY table_name, column_name;

-- Archived data snapshot by module
SELECT 'customers' AS module, COUNT(*) AS archived_count FROM customers WHERE is_deleted = TRUE
UNION ALL SELECT 'suppliers', COUNT(*) FROM suppliers WHERE is_deleted = TRUE
UNION ALL SELECT 'products', COUNT(*) FROM products WHERE is_deleted = TRUE
UNION ALL SELECT 'purchase_orders', COUNT(*) FROM purchase_orders WHERE is_deleted = TRUE
UNION ALL SELECT 'goods_receipt_notes', COUNT(*) FROM goods_receipt_notes WHERE is_deleted = TRUE
UNION ALL SELECT 'quotations', COUNT(*) FROM quotations WHERE is_deleted = TRUE
UNION ALL SELECT 'sales_orders', COUNT(*) FROM sales_orders WHERE is_deleted = TRUE
UNION ALL SELECT 'sales_invoices', COUNT(*) FROM sales_invoices WHERE is_deleted = TRUE
UNION ALL SELECT 'payments', COUNT(*) FROM payments WHERE is_deleted = TRUE
UNION ALL SELECT 'stock_ledger', COUNT(*) FROM stock_ledger WHERE is_deleted = TRUE
ORDER BY module;

-- Refresh current_stock view
REFRESH MATERIALIZED VIEW CONCURRENTLY current_stock;

