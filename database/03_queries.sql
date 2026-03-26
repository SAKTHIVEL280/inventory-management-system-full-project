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
ORDER BY tbl;

-- Verify admin exists
SELECT id, email, role, is_active, force_password_change
FROM users
WHERE email = 'admin@company.com';

-- Refresh current_stock view
REFRESH MATERIALIZED VIEW CONCURRENTLY current_stock;

