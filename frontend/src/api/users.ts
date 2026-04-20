import { apiClient } from './client';
import {
  PaginatedResponse,
  UserManagement,
  UserCreateRequest,
  UserUpdateRequest,
  UserPermissionsRequest,
} from '../types';

export const usersApi = {
  list: async (): Promise<PaginatedResponse<UserManagement>> => {
    const response = await apiClient.get<PaginatedResponse<UserManagement>>('/api/v2/users');
    return response.data;
  },

  create: async (payload: UserCreateRequest): Promise<UserManagement> => {
    const response = await apiClient.post<UserManagement>('/api/v2/users', payload);
    return response.data;
  },

  update: async (id: string, payload: UserUpdateRequest): Promise<UserManagement> => {
    const response = await apiClient.put<UserManagement>(`/api/v2/users/${id}`, payload);
    return response.data;
  },

  updatePermissions: async (id: string, payload: UserPermissionsRequest): Promise<UserManagement> => {
    const response = await apiClient.patch<UserManagement>(`/api/v2/users/${id}/permissions`, payload);
    return response.data;
  },

  clearPermissions: async (id: string): Promise<UserManagement> => {
    const response = await apiClient.delete<UserManagement>(`/api/v2/users/${id}/permissions`);
    return response.data;
  },
};

export const deleteUser = async (id: string): Promise<void> => {
  await apiClient.delete(`/api/v2/users/${id}`);
};

