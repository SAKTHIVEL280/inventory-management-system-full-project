/**
 * Return Delivery Note (RDN) API client.
 */
import { apiClient } from './client';
import type {
  RDN,
  RDNCreatePayload,
  RDNCustomizationOptions,
  RDNDetailResponse,
  RDNOverviewResponse,
  RDNCreditNoteDetailResponse,
  RDNCreditNoteOverviewResponse,
  RDNUpdatePayload,
} from '../types';

export const rdnApi = {
  list: async (params?: {
    search?: string;
    status?: string;
    page?: number;
    page_size?: number;
  }): Promise<RDNOverviewResponse> => {
    const response = await apiClient.get<RDNOverviewResponse>('/api/v2/rdn', { params });
    return response.data;
  },

  get: async (id: string): Promise<RDNDetailResponse> => {
    const response = await apiClient.get<RDNDetailResponse>(`/api/v2/rdn/${id}`);
    return response.data;
  },

  getCustomizationOptions: async (): Promise<RDNCustomizationOptions> => {
    const response = await apiClient.get<RDNCustomizationOptions>('/api/v2/rdn/customization-options');
    return response.data;
  },

  create: async (payload: RDNCreatePayload): Promise<RDN> => {
    const response = await apiClient.post<RDN>('/api/v2/rdn', payload);
    return response.data;
  },

  update: async (id: string, payload: RDNUpdatePayload): Promise<RDN> => {
    const response = await apiClient.put<RDN>(`/api/v2/rdn/${id}`, payload);
    return response.data;
  },

  confirm: async (id: string): Promise<RDN> => {
    const response = await apiClient.post<RDN>(`/api/v2/rdn/${id}/confirm`, {});
    return response.data;
  },

  cancel: async (id: string): Promise<RDN> => {
    const response = await apiClient.post<RDN>(`/api/v2/rdn/${id}/cancel`, {});
    return response.data;
  },

  listCreditNotes: async (params?: {
    search?: string;
    status?: string;
    page?: number;
    page_size?: number;
  }): Promise<RDNCreditNoteOverviewResponse> => {
    const response = await apiClient.get<RDNCreditNoteOverviewResponse>('/api/v2/rdn/credit-notes', { params });
    return response.data;
  },

  getCreditNote: async (id: string): Promise<RDNCreditNoteDetailResponse> => {
    const response = await apiClient.get<RDNCreditNoteDetailResponse>(`/api/v2/rdn/credit-notes/${id}`);
    return response.data;
  },
};
