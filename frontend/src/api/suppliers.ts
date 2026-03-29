import { apiClient } from './client';
import { Supplier, PaginatedResponse } from '../types';

type CreateSupplierPayload = {
  supplier_code?: string | null;
  company_name: string;
  contact_person?: string | null;
  email?: string | null;
  phone: string;
  alternate_phone?: string | null;
  gstin?: string | null;
  pan?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  state?: string | null;
  state_code?: string | null;
  pincode?: string | null;
  bank_name?: string | null;
  bank_account_no?: string | null;
  bank_ifsc?: string | null;
  place_of_supply?: string | null;
  payment_terms_days: number;
  opening_balance: number;
  opening_balance_type: 'dr' | 'cr';
  is_active: boolean;
};

export const suppliersApi = {
  list: async (): Promise<PaginatedResponse<Supplier>> => {
    const response = await apiClient.get<PaginatedResponse<Supplier>>('/api/v1/suppliers');
    return response.data;
  },

  get: async (id: string): Promise<Supplier> => {
    const response = await apiClient.get<Supplier>(`/api/v1/suppliers/${id}`);
    return response.data;
  },

  create: async (payload: CreateSupplierPayload): Promise<Supplier> => {
    const response = await apiClient.post<Supplier>('/api/v1/suppliers', payload);
    return response.data;
  },

  update: async (id: string, payload: Partial<CreateSupplierPayload>): Promise<Supplier> => {
    const response = await apiClient.put<Supplier>(`/api/v1/suppliers/${id}`, payload);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/v1/suppliers/${id}`);
  },
};
