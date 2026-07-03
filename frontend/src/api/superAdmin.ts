import { apiClient } from './client';

// Super Admin portal (M6 ↔ BE-221). Platform-level; only super admins may call.
export interface Tenant {
  id: string;
  name: string;
  gstin: string | null;
  contact_person_name: string | null;
  contact_number: string | null;
  email: string | null;
  phone: string | null;
  website: string | null;
  business_category: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  pincode: string | null;
  business_address: string | null;
  subscription_plan: string;
  account_status: string | null;
  payment_status: string | null;
  onboarding_date: string | null;
  subscription_start_date: string | null;
  subscription_expiry_date: string | null;
  tenant_code: string | null;
  user_limit: number;
  total_sales_invoices?: number;
  total_purchase_orders?: number;
  active_users?: number;
  admin_temporary_password?: string;
  admin_email?: string;
}

export interface ServiceInvoiceDetailItem {
  sr_no: number;
  item_name: string;
  description?: string | null;
  hsn_sac_code?: string | null;
  quantity: number;
  basic_price: number;
  discount_percent: number;
  discount_amount: number;
  is_free: boolean;
  taxable_amount: number;
  gst_rate: number;
  cgst_amount: number;
  sgst_amount: number;
  igst_amount: number;
  total_amount: number;
}

export interface ServiceInvoiceDetail {
  id: string;
  invoice_number: string;
  invoice_date: string;
  due_date: string | null;
  customer_name: string;
  customer_gstin: string | null;
  customer_email: string | null;
  customer_contact: string | null;
  billing_address: string | null;
  supply_type: string;
  subtotal: number;
  total_discount: number;
  total_taxable_amount: number;
  total_cgst: number;
  total_sgst: number;
  total_igst: number;
  total_gst: number;
  grand_total: number;
  amount_in_words: string | null;
  status: string;
  payment_status: string;
  notes: string | null;
  cancel_reason: string | null;
  items: ServiceInvoiceDetailItem[];
}

export interface RaiseServiceInvoiceItem {
  item_name: string;
  description?: string;
  hsn_sac_code: string;
  quantity: number;
  basic_price: number; // paise
  discount_percent: number;
  is_free: boolean;
  gst_rate: number;
}

export interface RaiseServiceInvoicePayload {
  invoice_date?: string;
  due_date?: string;
  supply_type: string;
  notes?: string;
  items: RaiseServiceInvoiceItem[];
}

export interface AuditLogEntry {
  created_at: string | null;
  username: string | null;
  action: string | null;
  action_type: string | null;
  module: string | null;
  description: string | null;
  status: string | null;
  ip_address: string | null;
}

export interface PlatformDashboard {
  total_erp_customers: number;
  active_erp_customers: number;
  inactive_erp_customers: number;
  total_sales_invoices: number;
  total_purchase_orders: number;
  total_service_invoices?: number;
  revenue_mtd?: number;
  revenue_ytd?: number;
  plan_distribution: Record<string, number>;
  expiring_subscriptions_30d: number;
}

export interface TenantCreatePayload {
  name: string;
  gstin?: string;
  contact_person_name?: string;
  contact_number?: string;
  email?: string;
  phone?: string;
  website?: string;
  business_category?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  country?: string;
  pincode?: string;
  subscription_plan: string;
  account_status?: string;
  payment_status?: string;
  subscription_start_date?: string;
  subscription_expiry_date?: string;
  tenant_code?: string;
  admin_full_name: string;
  admin_email: string;
  admin_password?: string;
}

// Edit "any field" of an existing tenant (BRD §4.3). Admin fields are not editable
// here (the tenant admin manages their own credentials; password reset is separate).
export interface TenantUpdatePayload {
  name?: string;
  gstin?: string;
  contact_person_name?: string;
  contact_number?: string;
  email?: string;
  phone?: string;
  website?: string;
  business_category?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  country?: string;
  pincode?: string;
  subscription_start_date?: string;
  subscription_expiry_date?: string;
  payment_status?: string;
  tenant_code?: string;
}

export interface PlatformCompany {
  id?: string;
  name?: string | null;
  legal_name?: string | null;
  gstin?: string | null;
  gstin_status?: string | null;
  pan?: string | null;
  import_export_number?: string | null;
  company_director_name?: string | null;
  company_director_contact?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  state_code?: string | null;
  pincode?: string | null;
  phone?: string | null;
  email?: string | null;
  website?: string | null;
  bank_name?: string | null;
  account_holder_name?: string | null;
  bank_account_no?: string | null;
  bank_ifsc?: string | null;
  bank_branch?: string | null;
  logo_url?: string | null;
  ambassador_logo_url?: string | null;
  logo_data_url?: string | null;
  ambassador_logo_data_url?: string | null;
}

const BASE = '/api/v2/admin';

export const superAdminApi = {
  dashboard: async (): Promise<PlatformDashboard> => {
    const r = await apiClient.get<PlatformDashboard>(`${BASE}/dashboard`);
    return r.data;
  },
  listTenants: async (params: { plan?: string; status?: string; search?: string } = {}) => {
    const r = await apiClient.get<{ tenants: Tenant[]; count: number }>(`${BASE}/tenants`, { params });
    return r.data;
  },
  getTenant: async (id: string): Promise<Tenant> => {
    const r = await apiClient.get<Tenant>(`${BASE}/tenants/${id}`);
    return r.data;
  },
  createTenant: async (payload: TenantCreatePayload): Promise<Tenant> => {
    const r = await apiClient.post<Tenant>(`${BASE}/tenants`, payload);
    return r.data;
  },
  updateTenant: async (id: string, payload: TenantUpdatePayload): Promise<Tenant> => {
    const r = await apiClient.put<Tenant>(`${BASE}/tenants/${id}`, payload);
    return r.data;
  },
  changePlan: async (id: string, subscription_plan: string): Promise<Tenant> => {
    const r = await apiClient.post<Tenant>(`${BASE}/tenants/${id}/plan`, { subscription_plan });
    return r.data;
  },
  renew: async (id: string, payload: { subscription_start_date?: string; subscription_expiry_date: string; payment_status?: string }) => {
    const r = await apiClient.post<Tenant>(`${BASE}/tenants/${id}/renew`, payload);
    return r.data;
  },
  changeStatus: async (id: string, account_status: string): Promise<Tenant> => {
    const r = await apiClient.post<Tenant>(`${BASE}/tenants/${id}/status`, { account_status });
    return r.data;
  },
  resetAdminPassword: async (id: string, new_password?: string) => {
    const r = await apiClient.post<{ admin_email: string; temporary_password?: string }>(
      `${BASE}/tenants/${id}/reset-admin-password`,
      { new_password },
    );
    return r.data;
  },
  impersonate: async (id: string) => {
    const r = await apiClient.post<{ access_token: string; token_type: string; impersonating: string }>(
      `${BASE}/tenants/${id}/impersonate`,
    );
    return r.data;
  },
  auditTrail: async (
    id: string,
    params: { user?: string; date_from?: string; date_to?: string; page?: number; page_size?: number } = {},
  ) => {
    const r = await apiClient.get<{ tenant_id: string; total: number; page: number; page_size: number; count: number; logs: AuditLogEntry[] }>(
      `${BASE}/tenants/${id}/audit-logs`, { params },
    );
    return r.data;
  },
  raiseServiceInvoice: async (id: string, payload: RaiseServiceInvoicePayload) => {
    const r = await apiClient.post<{ invoice_number: string; grand_total: number }>(
      `${BASE}/tenants/${id}/service-invoice`, payload,
    );
    return r.data;
  },
  // Invoice History (§8.4): all platform invoices, optionally filtered by tenant.
  listServiceInvoices: async (params: { tenant_id?: string; status?: string; search?: string } = {}) => {
    const r = await apiClient.get<{ count: number; service_invoices: ServiceInvoiceDetail[] }>(
      `${BASE}/service-invoices`, { params },
    );
    return r.data;
  },
  getServiceInvoice: async (invoiceId: string) => {
    const r = await apiClient.get<ServiceInvoiceDetail>(`${BASE}/service-invoices/${invoiceId}`);
    return r.data;
  },
  markServiceInvoicePaid: async (invoiceId: string) => {
    const r = await apiClient.post<ServiceInvoiceDetail>(`${BASE}/service-invoices/${invoiceId}/mark-paid`);
    return r.data;
  },
  cancelServiceInvoice: async (invoiceId: string, reason: string) => {
    const r = await apiClient.post<ServiceInvoiceDetail>(`${BASE}/service-invoices/${invoiceId}/cancel`, { reason });
    return r.data;
  },
  emailServiceInvoice: async (invoiceId: string) => {
    const r = await apiClient.post<{ invoice_number: string; recipient: string; delivery: string; message: string }>(
      `${BASE}/service-invoices/${invoiceId}/email`,
    );
    return r.data;
  },
  // Download as PDF (§8.4) — fetch as blob via the API client (correct origin + auth).
  downloadServiceInvoicePdf: async (invoiceId: string, invoiceNumber: string) => {
    const r = await apiClient.get(`${BASE}/service-invoices/${invoiceId}/pdf`, { responseType: 'blob' });
    const url = window.URL.createObjectURL(r.data as Blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${invoiceNumber.replace(/\//g, '-')}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },
  // Platform (Mecandria) seller company profile.
  getCompanyProfile: async (): Promise<PlatformCompany> => {
    const r = await apiClient.get<PlatformCompany>(`${BASE}/company`);
    return r.data;
  },
  updateCompanyProfile: async (payload: PlatformCompany): Promise<PlatformCompany> => {
    const r = await apiClient.put<PlatformCompany>(`${BASE}/company`, payload);
    return r.data;
  },
  uploadCompanyLogo: async (file: File): Promise<{ logo_url: string }> => {
    const fd = new FormData();
    fd.append('logo', file);
    const r = await apiClient.post<{ logo_url: string }>(`${BASE}/company/logo`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return r.data;
  },
  uploadCompanyAmbassadorLogo: async (file: File): Promise<{ ambassador_logo_url: string }> => {
    const fd = new FormData();
    fd.append('logo', file);
    const r = await apiClient.post<{ ambassador_logo_url: string }>(`${BASE}/company/ambassador-logo`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return r.data;
  },
  removeCompanyAmbassadorLogo: async (): Promise<void> => {
    await apiClient.delete(`${BASE}/company/ambassador-logo`);
  },
  exportUrl: `${BASE}/tenants/export`,
};
