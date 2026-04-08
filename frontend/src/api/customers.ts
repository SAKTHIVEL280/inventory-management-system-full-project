import { apiClient } from './client';
import { Customer, CustomerCustomizationOptions, PaginatedResponse } from '../types';

type CreateCustomerPayload = {
  customer_code?: string | null;
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
  customer_type: 'regular' | 'dealer' | 'distributor' | 'retail';
  business_type?: 'domestic' | 'international';
  billing_address_line1?: string | null;
  billing_address_line2?: string | null;
  billing_city?: string | null;
  billing_state?: string | null;
  billing_state_code?: string | null;
  billing_country?: string | null;
  billing_pincode?: string | null;
  shipping_address_line1?: string | null;
  shipping_address_line2?: string | null;
  shipping_city?: string | null;
  shipping_state?: string | null;
  shipping_state_code?: string | null;
  shipping_country?: string | null;
  shipping_pincode?: string | null;
  same_as_billing: boolean;
  credit_limit: number;
  payment_terms_days?: number | null;
  currency_code: string;
  opening_balance: number;
  opening_balance_type: 'dr' | 'cr';
  is_active: boolean;
};

type ListCustomersParams = {
  search?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
};

export const customersApi = {
  list: async (params: ListCustomersParams = {}): Promise<PaginatedResponse<Customer>> => {
    const response = await apiClient.get<PaginatedResponse<Customer>>('/api/v1/customers', { params });
    return response.data;
  },

  get: async (id: string): Promise<Customer> => {
    const response = await apiClient.get<Customer>(`/api/v1/customers/${id}`);
    return response.data;
  },

  getCustomizationOptions: async (): Promise<CustomerCustomizationOptions> => {
    const response = await apiClient.get<CustomerCustomizationOptions>('/api/v1/customers/customization-options');
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
