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

-- Default Admin User
-- NOTE:
-- The hashed_password MUST be a valid bcrypt hash of "Admin@123".
-- If you change the password, you must replace the hash accordingly.
INSERT INTO users (full_name, email, hashed_password, role, is_active, force_password_change)
SELECT
  'System Administrator',
  'admin@company.com',
  '$2b$12$K7FoG9K.8fI.ZeLtyrWWaujcON4a9.5P6Ky/.qatWZy9iTPC88KQq',
  'admin',
  TRUE,
  TRUE
WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'admin@company.com');

COMMIT;

