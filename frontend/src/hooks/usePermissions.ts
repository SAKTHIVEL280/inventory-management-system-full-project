/**
 * usePermissions Hook
 * 
 * Check if current user has a specific permission.
 * Uses backend's authoritative effective_access list from auth token.
 */

import { useAuthStore } from '../store/auth';
import { PermissionScope } from '../types';
import { useCallback, useMemo } from 'react';

export const usePermissions = () => {
  const user = useAuthStore((state) => state.user);

  const can = useCallback((permission: PermissionScope | string): boolean => {
    if (!user) return false;
    return user.effective_access?.includes(permission) ?? false;
  }, [user]);

  const canWrite = useCallback((scope: string): boolean => {
    return can(`${scope}_write` as PermissionScope);
  }, [can]);

  const canRead = useCallback((scope: string): boolean => {
    return can(`${scope}_read` as PermissionScope);
  }, [can]);

  return useMemo(() => ({
    can,
    canRead,
    canWrite,
    isAdmin: user?.role === 'admin' || user?.role === 'doctor' || user?.role === 'accounts',
    isAccounting: user?.role === 'accounts',
  }), [can, canRead, canWrite, user]);
};
