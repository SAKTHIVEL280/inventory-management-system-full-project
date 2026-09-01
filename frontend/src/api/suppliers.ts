import { apiClient } from './client';
import { Supplier, SupplierCustomizationOptions, PaginatedResponse } from '../types';

type CreateSupplierPayload = {
  supplier_code?: string | null;
  company_name: string;
  company_director_name?: string | null;
  company_director_contact?: string | null;
  contact_person?: string | null;
  email?: string | null;
  phone: string;
  alternate_phone?: string | null;
  gstin_status?: 'registered' | 'non-registered';
  gstin?: string | null;
  pan?: string | null;
  business_type?: 'domestic' | 'international';
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  state?: string | null;
  state_code?: string | null;
  billing_country?: string | null;
  pincode?: string | null;
  bank_name?: string | null;
  bank_account_no?: string | null;
  bank_ifsc?: string | null;
  place_of_supply?: string | null;
  payment_terms_days: number;
  currency_code: string;
  opening_balance: number;
  opening_balance_type: 'dr' | 'cr';
  is_active: boolean;
};

type ListSuppliersParams = {
  search?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
};

export const suppliersApi = {
  list: async (params: ListSuppliersParams = {}): Promise<PaginatedResponse<Supplier>> => {
    const response = await apiClient.get<PaginatedResponse<Supplier>>('/api/v2/suppliers', { params });
    return response.data;
  },

  // Download the tenant's suppliers as an .xlsx (respects search / active filter).
  exportXlsx: (params: { search?: string; is_active?: boolean } = {}) =>
    apiClient.get('/api/v2/suppliers/export', { params, responseType: 'blob' }),

  get: async (id: string): Promise<Supplier> => {
    const response = await apiClient.get<Supplier>(`/api/v2/suppliers/${id}`);
    return response.data;
  },

  getCustomizationOptions: async (): Promise<SupplierCustomizationOptions> => {
    const response = await apiClient.get<SupplierCustomizationOptions>('/api/v2/suppliers/customization-options');
    return response.data;
  },

  create: async (payload: CreateSupplierPayload): Promise<Supplier> => {
    const response = await apiClient.post<Supplier>('/api/v2/suppliers', payload);
    return response.data;
  },

  update: async (id: string, payload: Partial<CreateSupplierPayload>): Promise<Supplier> => {
    const response = await apiClient.put<Supplier>(`/api/v2/suppliers/${id}`, payload);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/v2/suppliers/${id}`);
  },
};

