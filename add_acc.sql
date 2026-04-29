-- SQL script to seed an Admin account
-- Email: Admin@company.com
-- Password: Admin@123

INSERT INTO users (
    id, 
    full_name, 
    email, 
    hashed_password, 
    role, 
    is_active, 
    is_deleted, 
    created_at, 
    updated_at,
    failed_login_attempts,
    force_password_change
)
VALUES (
    gen_random_uuid(), 
    'Admin User', 
    'Admin@company.com', 
    '$2b$12$tCMAJYEEpPeT9tabxZXY4uk0.pRN8opdVidDo2ecseZ.avor7L4nG', 
    'admin', 
    true, 
    false, 
    CURRENT_TIMESTAMP, 
    CURRENT_TIMESTAMP,
    0,
    false
)
ON CONFLICT (email) DO UPDATE SET 
    hashed_password = EXCLUDED.hashed_password,
    role = 'admin',
    is_active = true,
    is_deleted = false,
    updated_at = CURRENT_TIMESTAMP,
    force_password_change = false;
