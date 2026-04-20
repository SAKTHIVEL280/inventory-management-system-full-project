/**
 * Auth API Client
 * 
 * Centralized place for all auth-related API calls.
 * No fetch/axios calls in components - all API logic here.
 */

import { LoginRequest, AuthToken, ChangePasswordRequest } from '../types';
import type { User } from '../types';
import { apiClient, ApiRequestConfig } from './client';

class AuthApiClient {
  private readonly silentConfig: ApiRequestConfig = { skipErrorToast: true };

  async login(credentials: LoginRequest): Promise<AuthToken> {
    const response = await apiClient.post<AuthToken>(
      '/api/v2/auth/login',
      credentials,
      this.silentConfig
    );
    return response.data;
  }

  async refresh(): Promise<AuthToken> {
    const response = await apiClient.post<AuthToken>(
      '/api/v2/auth/refresh',
      undefined,
      this.silentConfig
    );
    return response.data;
  }

  async getMe(): Promise<User> {
    const response = await apiClient.get<User>(
      '/api/v2/auth/me',
      this.silentConfig
    );
    return response.data;
  }

  async logout(): Promise<void> {
    try {
      await apiClient.post('/api/v2/auth/logout', {}, this.silentConfig);
    } catch {
      // Ignore errors on logout
    }
  }

  async changePassword(request: ChangePasswordRequest): Promise<{ message: string }> {
    const response = await apiClient.post<{ message: string }>(
      '/api/v2/auth/change-password',
      request,
      this.silentConfig
    );
    return response.data;
  }
}

export const authApi = new AuthApiClient();
