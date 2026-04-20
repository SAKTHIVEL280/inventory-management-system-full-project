-- IMS Seed Data
-- Required seed to let the app boot and login.

BEGIN;

-- Company: single row (placeholder)
INSERT INTO company (name)
SELECT 'Your Company Name'
WHERE NOT EXISTS (SELECT 1 FROM company);

-- Units of Measure
INSERT INTO units_of_measure (name, abbreviation, is_active)
SELECT * FROM (VALUES
  ('Piece','PCS',TRUE),
  ('Kilogram','KG',TRUE),
  ('Gram','G',TRUE),
  ('Litre','LTR',TRUE),
  ('Millilitre','ML',TRUE),
  ('Box','BOX',TRUE),
  ('Pack','PACK',TRUE),
  ('Meter','MTR',TRUE),
  ('Square Meter','SQM',TRUE),
  ('Numbers','NOS',TRUE)
) AS v(name, abbreviation, is_active)
WHERE NOT EXISTS (SELECT 1 FROM units_of_measure u WHERE u.abbreviation = v.abbreviation);

-- Default Product Category
INSERT INTO product_categories (name, description, is_active)
SELECT 'General', 'Default category', TRUE
WHERE NOT EXISTS (SELECT 1 FROM product_categories WHERE name = 'General');

-- Admin user bootstrap is intentionally handled by backend/app/utils/seed.py
-- using IMS_ADMIN_EMAIL / IMS_ADMIN_PASSWORD or generated secure credentials.

COMMIT;

