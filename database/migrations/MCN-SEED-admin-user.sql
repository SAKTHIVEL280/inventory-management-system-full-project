

INSERT INTO users (
    full_name,
    email,
    hashed_password,
    role,
    is_active,
    force_password_change,
    company_id
)
VALUES (
    'Administrator',
    'admin@mecandria.com',
    '$2b$12$synI0OJVXmpUC8FAIGnVpurmk5yfykjH7QpDoVEVIm4iKCIWkYxHG',  -- bcrypt('admin@123')
    'admin',
    TRUE,
    FALSE,
    (SELECT id FROM company ORDER BY created_at NULLS FIRST LIMIT 1)
)
ON CONFLICT (email) DO UPDATE
SET hashed_password        = EXCLUDED.hashed_password,
    role                   = 'admin',
    is_active              = TRUE,
    force_password_change  = FALSE,
    failed_login_attempts  = 0,
    locked_until           = NULL,
    is_deleted             = FALSE,
    deleted_at             = NULL,
    company_id             = COALESCE(users.company_id, EXCLUDED.company_id),
    updated_at             = NOW();
