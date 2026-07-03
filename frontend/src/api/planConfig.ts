import { apiClient } from './client';

// Super Admin → Plan Configuration (DB-backed subscription plans). Platform-level.
export interface PlanConfig {
  plan_key: string;
  name: string;
  price_paise: number;
  billing_period: string; // 'none' | 'monthly' | 'yearly'
  user_limit: number;
  modules: string[];
  features: string[]; // read-only: auto-derived from enabled modules by the backend
  roles: string[];
  free_invoice_cap: number | null;
  is_active: boolean;
  sort_order: number;
}

export interface CatalogEntry {
  key: string;
  label: string;
}

export interface PlanConfigResponse {
  plans: PlanConfig[];
  module_catalog: CatalogEntry[];
  role_catalog: string[];
  billing_periods: string[];
}

// Partial update — only the fields the Super Admin changed are sent.
// Features are NOT included: they are auto-derived from `modules` on the backend.
export type PlanUpdatePayload = Partial<{
  name: string;
  price_paise: number;
  billing_period: string;
  user_limit: number;
  modules: string[];
  roles: string[];
  free_invoice_cap: number | null;
  is_active: boolean;
}>;

const BASE = '/api/v2/admin/plans';

export const planConfigApi = {
  list: async (): Promise<PlanConfigResponse> => {
    const r = await apiClient.get<PlanConfigResponse>(BASE);
    return r.data;
  },
  update: async (planKey: string, payload: PlanUpdatePayload) => {
    const r = await apiClient.put<{ plan: PlanConfig; message: string }>(`${BASE}/${planKey}`, payload);
    return r.data;
  },
};
