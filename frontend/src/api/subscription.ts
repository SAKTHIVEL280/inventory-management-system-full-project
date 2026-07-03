import { apiClient } from './client';

// Multi-tenant (M6): the calling tenant's plan entitlements + live usage.
export interface RoleCatalogEntry {
  role: string;
  color: string | null;
  label: string | null;
  available: boolean;
}

export interface SubscriptionInfo {
  plan: string;
  plan_name?: string;
  price_paise?: number;
  billing_period?: string;
  is_active?: boolean;
  modules: string[];
  features: string[];
  user_limit: number;
  roles: string[];
  free_invoice_cap: number | null;
  roles_catalog: RoleCatalogEntry[];
  company_id: string;
  company_name: string;
  account_status: string | null;
  payment_status: string | null;
  subscription_start_date: string | null;
  subscription_expiry_date: string | null;
  active_user_count: number;
}

export const subscriptionApi = {
  me: async (): Promise<SubscriptionInfo> => {
    const response = await apiClient.get<SubscriptionInfo>('/api/v2/subscription/me');
    return response.data;
  },
};
