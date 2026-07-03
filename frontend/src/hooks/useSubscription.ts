/**
 * useSubscription / useModuleAccess (Module M6)
 *
 * Loads the current tenant's plan entitlements (from /subscription/me) and
 * exposes helpers for plan-aware UI: hiding/locking modules not in the plan,
 * showing the active-plan banner, and FREE-cap warnings. This is the tenant-
 * capability layer; it complements usePermissions (the user-role layer).
 */
import { useQuery } from '@tanstack/react-query';
import { useMemo, useCallback } from 'react';
import { subscriptionApi, SubscriptionInfo } from '../api/subscription';
import { useAuthStore } from '../store/auth';

export const useSubscription = () => {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  // Super Admins have no tenant — /subscription/me is tenant-only and would 403.
  const isSuperAdmin = useAuthStore((s) => !!s.user?.is_super_admin);
  // Key the cache by tenant so switching/logging-in as a different tenant never
  // shows another tenant's plan/limits (fixes stale "X/Y on PLAN" cross-tenant data).
  const companyId = useAuthStore((s) => s.user?.company_id ?? null);
  const userId = useAuthStore((s) => s.user?.id ?? null);

  const query = useQuery<SubscriptionInfo>({
    queryKey: ['subscription', 'me', companyId, userId],
    queryFn: subscriptionApi.me,
    enabled: isAuthenticated && !isSuperAdmin && !!userId,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const data = query.data;

  const canAccessModule = useCallback(
    (module: string): boolean => {
      // While loading or if entitlements are unavailable, don't hard-block the
      // UI — the backend remains the authoritative gate (returns 403 if denied).
      if (!data) return true;
      return data.modules.includes(module);
    },
    [data],
  );

  const isModuleLocked = useCallback(
    (module: string): boolean => !!data && !data.modules.includes(module),
    [data],
  );

  const canAccessFeature = useCallback(
    (feature: string): boolean => {
      // Backend remains authoritative; while loading, don't hard-block the UI.
      if (!data) return true;
      return (data.features ?? []).includes(feature);
    },
    [data],
  );

  return useMemo(
    () => ({
      subscription: data,
      isLoading: query.isLoading,
      plan: data?.plan ?? null,
      planName: data?.plan_name ?? null,
      modules: data?.modules ?? [],
      features: data?.features ?? [],
      canAccessModule,
      isModuleLocked,
      canAccessFeature,
      userLimit: data?.user_limit ?? null,
      activeUserCount: data?.active_user_count ?? null,
      atUserLimit: !!data && data.active_user_count >= data.user_limit,
      expiryDate: data?.subscription_expiry_date ?? null,
      rolesCatalog: data?.roles_catalog ?? [],
    }),
    [data, query.isLoading, canAccessModule, isModuleLocked, canAccessFeature],
  );
};
