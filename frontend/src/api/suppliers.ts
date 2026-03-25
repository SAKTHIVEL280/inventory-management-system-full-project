import { apiClient } from './client';
import { Supplier, PaginatedResponse } from '../types';

export const suppliersApi = {
  list: async (): Promise<PaginatedResponse<Supplier>> => {
    const response = await apiClient.get<PaginatedResponse<Supplier>>('/api/v1/suppliers');
    return response.data;
  },

  create: async (payload: Omit<Supplier, 'id'>): Promise<Supplier> => {
    const response = await apiClient.post<Supplier>('/api/v1/suppliers', payload);
    return response.data;
  },
};
