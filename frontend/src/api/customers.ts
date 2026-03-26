import { apiClient } from './client';
import { Customer, PaginatedResponse } from '../types';

type CreateCustomerPayload = {
  customer_code?: string | null;
  company_name: string;
  contact_person?: string | null;
  email?: string | null;
  phone: string;
  alternate_phone?: string | null;
  gstin?: string | null;
  pan?: string | null;
  customer_type: 'regular' | 'dealer' | 'distributor' | 'retail';
  billing_address_line1?: string | null;
  billing_address_line2?: string | null;
  billing_city?: string | null;
  billing_state?: string | null;
  billing_state_code?: string | null;
  billing_pincode?: string | null;
  shipping_address_line1?: string | null;
  shipping_address_line2?: string | null;
  shipping_city?: string | null;
  shipping_state?: string | null;
  shipping_state_code?: string | null;
  shipping_pincode?: string | null;
  same_as_billing: boolean;
  credit_limit: number;
  payment_terms_days: number;
  opening_balance: number;
  opening_balance_type: 'dr' | 'cr';
  is_active: boolean;
};

export const customersApi = {
  list: async (): Promise<PaginatedResponse<Customer>> => {
    const response = await apiClient.get<PaginatedResponse<Customer>>('/api/v1/customers');
    return response.data;
  },

  get: async (id: string): Promise<Customer> => {
    const response = await apiClient.get<Customer>(`/api/v1/customers/${id}`);
    return response.data;
  },

  create: async (payload: CreateCustomerPayload): Promise<Customer> => {
    const response = await apiClient.post<Customer>('/api/v1/customers', payload);
    return response.data;
  },

  update: async (id: string, payload: Partial<CreateCustomerPayload>): Promise<Customer> => {
    const response = await apiClient.put<Customer>(`/api/v1/customers/${id}`, payload);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/v1/customers/${id}`);
  },
};
