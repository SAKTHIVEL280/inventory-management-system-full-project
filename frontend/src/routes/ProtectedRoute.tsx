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
import { PermissionScope } from '../types';

interface ProtectedRouteProps {
  children: ReactNode;
  requiredPermission?: PermissionScope | PermissionScope[];
  requiredRole?: string | string[];
}

export const ProtectedRoute = ({
  children,
  requiredPermission,
  requiredRole,
}: ProtectedRouteProps) => {
  const { user, isAuthenticated } = useAuthStore();

  // No token - redirect to login
  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
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
        to="/dashboard"
        className="mt-4 inline-block px-4 py-2 bg-primary text-white rounded hover:bg-opacity-90"
      >
        Back to Dashboard
      </Link>
    </div>
  </main>
);
