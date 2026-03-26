/**
 * usePermissions Hook
 * 
 * Check if current user has a specific permission.
 * Uses backend's authoritative effective_access list from auth token.
 */

import { useAuthStore } from '../store/auth';
import { PermissionScope } from '../types';

export const usePermissions = () => {
  const user = useAuthStore((state) => state.user);

  const can = (permission: PermissionScope | string): boolean => {
    if (!user) return false;
    return user.effective_access?.includes(permission) ?? false;
  };

  const canWrite = (scope: string): boolean => {
    return can(`${scope}_write` as PermissionScope);
  };

  const canRead = (scope: string): boolean => {
    return can(`${scope}_read` as PermissionScope);
  };

  return {
    can,
    canRead,
    canWrite,
    isAdmin: user?.role === 'admin',
    isAccounting: user?.role === 'accounting',
    isSales: user?.role === 'sales',
    isInventory: user?.role === 'inventory',
  };
};
