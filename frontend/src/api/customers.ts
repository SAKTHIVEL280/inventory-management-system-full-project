import { apiClient } from './client';
import { Customer, PaginatedResponse } from '../types';

export const customersApi = {
  list: async (): Promise<PaginatedResponse<Customer>> => {
    const response = await apiClient.get<PaginatedResponse<Customer>>('/api/v1/customers');
    return response.data;
  },

  create: async (payload: Omit<Customer, 'id'>): Promise<Customer> => {
    const response = await apiClient.post<Customer>('/api/v1/customers', payload);
    return response.data;
  },
};
