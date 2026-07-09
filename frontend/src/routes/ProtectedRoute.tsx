/**
 * ProtectedRoute Component
 * 
 * Guards routes that require authentication and/or specific permissions.
 * - No token: redirect to /login
 * - Token exists but insufficient permissions: show 403 page (do not redirect)
 * - Token exists and sufficient permissions: render children
 */

import { ReactNode } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { useAuthStore } from '../store/auth';
import { useSubscription } from '../hooks/useSubscription';
import { PermissionScope } from '../types';
import SubscriptionExpiredPage from '../pages/SubscriptionExpiredPage';

const RouteSpinner = () => (
  <div className="flex items-center justify-center min-h-screen bg-gray-50" role="status" aria-live="polite">
    <div className="inline-block animate-spin rounded-full h-10 w-10 border-b-2 border-primary" />
  </div>
);

interface ProtectedRouteProps {
  children: ReactNode;
  requiredPermission?: PermissionScope | PermissionScope[];
  requiredRole?: string | string[];
  /** Subscription module this route belongs to. If the tenant's plan excludes it,
   *  the route redirects home (instead of letting the page fire an API call that
   *  would 403 with an "upgrade" toast). */
  requiredModule?: string;
}

export const ProtectedRoute = ({
  children,
  requiredPermission,
  requiredRole,
  requiredModule,
}: ProtectedRouteProps) => {
  const { user, isAuthenticated } = useAuthStore();
  const { canAccessModule, isExpired, isLoading: subLoading } = useSubscription();

  // No token - redirect to login
  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  // Subscription-expiry gate (front-line UX; the backend also 403s every tenant
  // API, so this can't be bypassed). Applies to ALL tenant routes. Super Admins
  // have no tenant plan and are unaffected. Wait for entitlements before deciding
  // so we never flash a real page. Renders the expired page in place (data is
  // preserved server-side and returns automatically once renewed).
  if (!user.is_super_admin) {
    if (subLoading) return <RouteSpinner />;
    if (isExpired) return <SubscriptionExpiredPage />;
  }

  // Plan-based module gate (BRD §5.5). Super Admins have no tenant plan and are
  // routed only to their own pages, so they bypass this. For tenant users, wait
  // until entitlements load before deciding (avoids the page mounting and firing
  // a module-locked API call); then redirect home if the plan excludes the module.
  if (requiredModule && !user.is_super_admin) {
    if (subLoading) {
      return <RouteSpinner />;
    }
    if (!canAccessModule(requiredModule)) {
      return <Navigate to="/" replace />;
    }
  }

  // Check role if specified
  if (requiredRole) {
    const roles = Array.isArray(requiredRole) ? requiredRole : [requiredRole];
    if (!roles.includes(user.role)) {
      return <ForbiddenPage />;
    }
  }

  // Check permission if specified
  if (requiredPermission) {
    const permissions = Array.isArray(requiredPermission)
      ? requiredPermission
      : [requiredPermission];

    const hasPermission = permissions.some((p) =>
      user.effective_access?.includes(p)
    );

    if (!hasPermission) {
      return <ForbiddenPage />;
    }
  }

  // All checks passed
  return <>{children}</>;
};

const ForbiddenPage = () => (
  <main className="flex items-center justify-center min-h-screen bg-gray-50" aria-labelledby="forbidden-title">
    <div className="text-center" role="alert" aria-live="assertive">
      <h1 className="text-4xl font-bold text-gray-900">403</h1>
      <p id="forbidden-title" className="mt-2 text-lg text-gray-600">Access Denied</p>
      <p className="mt-1 text-sm text-gray-500">
        You don't have permission to access this resource.
      </p>
      <Link
        to="/login"
        className="mt-4 inline-block px-4 py-2 bg-primary text-white rounded hover:bg-opacity-90"
      >
        Back to Login
      </Link>
    </div>
  </main>
);
