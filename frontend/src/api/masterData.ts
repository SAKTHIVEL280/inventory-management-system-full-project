import { apiClient } from './client';
import type {
  SalesManager,
  SalesManagerPayload,
  SalesManagersListResponse,
  Stockist,
  StockistPayload,
  StockistsListResponse,
} from '../types';

type ListParams = {
  search?: string;
  include_inactive?: boolean;
  page?: number;
  page_size?: number;
};

export const stockistsApi = {
  list: async (params: ListParams = {}): Promise<StockistsListResponse> => {
    const response = await apiClient.get<StockistsListResponse>('/api/v2/stockists', { params });
    return response.data;
  },
  create: async (payload: StockistPayload): Promise<Stockist> => {
    const response = await apiClient.post<Stockist>('/api/v2/stockists', payload);
    return response.data;
  },
  update: async (id: string, payload: Partial<StockistPayload>): Promise<Stockist> => {
    const response = await apiClient.put<Stockist>(`/api/v2/stockists/${id}`, payload);
    return response.data;
  },
  remove: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/v2/stockists/${id}`);
  },
};

export const salesManagersApi = {
  list: async (params: ListParams = {}): Promise<SalesManagersListResponse> => {
    const response = await apiClient.get<SalesManagersListResponse>('/api/v2/sales-managers', { params });
    return response.data;
  },
  create: async (payload: SalesManagerPayload): Promise<SalesManager> => {
    const response = await apiClient.post<SalesManager>('/api/v2/sales-managers', payload);
    return response.data;
  },
  update: async (id: string, payload: Partial<SalesManagerPayload>): Promise<SalesManager> => {
    const response = await apiClient.put<SalesManager>(`/api/v2/sales-managers/${id}`, payload);
    return response.data;
  },
  remove: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/v2/sales-managers/${id}`);
  },
};
