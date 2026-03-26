# WF-01: Authentication Workflow

## Overview
JWT-based authentication with access tokens (8 hours) and refresh tokens (7 days). Four roles: admin, accounting, sales, inventory. Every protected route requires a valid Bearer token. Access control uses role defaults plus optional admin-managed module overrides per user.

---

## Step-by-Step Flow

### Login
1. User opens `/login` page. If already authenticated (valid token in localStorage), redirect to `/dashboard`.
2. User enters email and password.
3. Frontend sends `POST /api/v1/auth/login` with `{ email, password }`.
4. Backend verifies email exists in users table (is_active=true, is_deleted=false).
5. Backend verifies bcrypt hash of password.
6. On success, backend returns `{ access_token, refresh_token, token_type, user }` where `user` includes `permission_overrides`, `effective_access`, and `force_password_change`.
7. Frontend stores access_token and refresh_token in localStorage.
8. Frontend stores user object in Zustand authStore.
9. Frontend redirects to `/dashboard`.
10. On failure (wrong credentials), backend returns 401. Frontend shows "Invalid email or password" error on form.

### Authenticated Requests
1. Every API request includes header: `Authorization: Bearer <access_token>`.
2. Backend middleware decodes and validates the JWT on every request.
3. If token is expired, backend returns 401.
4. Frontend Axios interceptor catches 401, attempts token refresh using refresh_token.
5. If refresh succeeds, retry the original request with new access_token.
6. If refresh fails (refresh token also expired), clear localStorage and redirect to `/login`.
7. Frontend must treat `user.effective_access` as the authoritative permission list for route guards and sidebar visibility.

### Token Refresh
1. Frontend sends `POST /api/v1/auth/refresh` with `{ refresh_token }`.
2. Backend validates refresh token, issues new access_token.
3. Frontend updates localStorage with new access_token.

### Logout
1. User clicks logout in top bar user menu.
2. Frontend sends `POST /api/v1/auth/logout`.
3. Frontend clears localStorage (removes both tokens and user object).
4. Frontend clears Zustand authStore.
5. Frontend redirects to `/login`.

### First Login (Password Change)
1. Admin seeds the database. Default admin password is `Admin@123`.
2. On first login, backend returns `{ force_password_change: true }` in the user object.
3. Frontend detects this flag and shows a "Change Password" modal before allowing navigation.
4. User must enter current password, new password, confirm new password.
5. New password must be minimum 8 characters, contain at least one uppercase, one number.
6. On successful change, `force_password_change` is set to false. User proceeds to dashboard.

---

## Protected Route Logic (Frontend)

```typescript
// routes/ProtectedRoute.tsx
// If no token: redirect to /login
// If token exists but effective_access is insufficient: show 403 page (do not redirect)
// If token exists and effective_access is sufficient: render children
```

---

## Role Permission Check (Frontend)

```typescript
// hooks/usePermissions.ts
const usePermissions = () => {
  const { user } = useAuthStore();

  const can = (permission: string): boolean => {
        const effectiveAccess = user.effective_access ?? [];
        return effectiveAccess.includes(permission);
  };

  return { can };
};

// Usage in any component
const { can } = usePermissions();
if (can('create_invoice')) { ... }
```

---

## Backend JWT Dependency

```python
# dependencies.py
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    try:
        payload = jose.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(401, "Invalid token")
    user = db.query(User).filter(User.id == user_id, User.is_active == True, User.is_deleted == False).first()
    if not user:
        raise HTTPException(401, "User not found or inactive")
    return user

def require_role(*roles: str):
    def dependency(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(403, detail="Insufficient permissions")
        return current_user
    return dependency
```

---

## Failure Scenarios and Handling

| Scenario | Backend Response | Frontend Action |
|---|---|---|
| Wrong password | 401 | Show inline form error |
| Inactive user | 401 | Show "Account disabled" error |
| Expired access token | 401 | Auto-refresh silently |
| Expired refresh token | 401 | Clear session, redirect to /login |
| Overrides reset by admin | 200 | Refresh `/auth/me`; UI falls back to role-default permissions |
| Insufficient role | 403 | Show permission error toast |
| Network error on login | — | Show "Cannot connect to server" error |
