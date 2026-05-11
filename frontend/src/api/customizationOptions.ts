import { apiClient } from './client';
import type {
  CustomizationOption,
  CustomizationOptionPayload,
  CustomizationOptionsListResponse,
} from '../types';

type ListParams = {
  module?: string;
  field_name?: string;
  search?: string;
  include_inactive?: boolean;
  page?: number;
  page_size?: number;
};

export const customizationOptionsApi = {
  list: async (params: ListParams = {}): Promise<CustomizationOptionsListResponse> => {
    const response = await apiClient.get<CustomizationOptionsListResponse>('/api/v2/customization-options', { params });
    return response.data;
  },

  create: async (payload: CustomizationOptionPayload): Promise<CustomizationOption> => {
    const response = await apiClient.post<CustomizationOption>('/api/v2/customization-options', payload);
    return response.data;
  },

  update: async (id: string, payload: Partial<CustomizationOptionPayload>): Promise<CustomizationOption> => {
    const response = await apiClient.put<CustomizationOption>(`/api/v2/customization-options/${id}`, payload);
    return response.data;
  },

  remove: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/v2/customization-options/${id}`);
  },
};
