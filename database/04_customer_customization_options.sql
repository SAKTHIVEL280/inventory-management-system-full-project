-- Customer customization options master
-- Date: April 7, 2026
-- Purpose: Make Country/Currency/State customer fields configurable and editable

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

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
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_customization_option_scope
ON customization_options (module, field_name, option_value);

CREATE INDEX IF NOT EXISTS ix_customization_options_module
ON customization_options (module);

CREATE INDEX IF NOT EXISTS ix_customization_options_field_name
ON customization_options (field_name);

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
  ('customer', 'state', 'Delhi', 'Delhi', 29, TRUE)
ON CONFLICT (module, field_name, option_value) DO NOTHING;

COMMIT;
