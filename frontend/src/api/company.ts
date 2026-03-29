import { apiClient } from './client';
import { Company } from '../types';

export const companyApi = {
  get: async (): Promise<Company> => {
    const response = await apiClient.get<Company>('/api/v1/company');
    return response.data;
  },

  update: async (payload: Company): Promise<Company> => {
    const response = await apiClient.put<Company>('/api/v1/company', payload);
    return response.data;
  },

  uploadLogo: async (file: File): Promise<{ logo_url: string }> => {
    const formData = new FormData();
    formData.append('logo', file);
    const response = await apiClient.post<{ logo_url: string }>('/api/v1/company/logo', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
};
