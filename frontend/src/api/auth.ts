/**
 * Auth API Client
 * 
 * Centralized place for all auth-related API calls.
 * No fetch/axios calls in components - all API logic here.
 */

import axios, { AxiosInstance } from 'axios';
import { LoginRequest, AuthToken, ChangePasswordRequest } from '../types';
import type { User } from '../types';
import { useAuthStore } from '../store/auth';
import { toast } from 'sonner';

const defaultApiBaseUrl =
  typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:8001`
    : 'http://localhost:8001';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl;

const authErrorToastHistory = new Map<string, number>();

const shouldShowToast = (message: string): boolean => {
  const now = Date.now();
  const last = authErrorToastHistory.get(message) || 0;
  if (now - last < 1500) {
    return false;
  }
  authErrorToastHistory.set(message, now);
  return true;
};

const getAuthErrorMessage = (error: unknown): string => {
  if (!axios.isAxiosError(error) || !error.response) {
    return 'Cannot reach server. Check internet/CORS/backend status and host (localhost vs 127.0.0.1).';
  }

  const status = error.response.status;
  const detail = (error.response.data as { detail?: unknown } | undefined)?.detail;

  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const joined = detail
      .map((d) => d?.msg || d?.message)
      .filter((m: unknown): m is string => typeof m === 'string' && m.trim().length > 0)
      .join(', ');
    if (joined) {
      return joined;
    }
  }

  if (status === 401) {
    return 'Invalid credentials or session expired.';
  }
  if (status === 403) {
    return 'You do not have permission to perform this action.';
  }
  if (status === 422) {
    return 'Some fields are invalid. Please correct and try again.';
  }
  if (status >= 500) {
    return 'Server error occurred. Please retry. If it continues, contact support.';
  }
  return 'Request failed. Please try again.';
};

class AuthApiClient {
  private axiosInstance: AxiosInstance;

  constructor() {
    this.axiosInstance = axios.create({
      baseURL: API_BASE_URL,
    });

    // Add request interceptor to include auth token
    this.axiosInstance.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('accessToken');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Add response interceptor to handle 401 and refresh token
    this.axiosInstance.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            const refreshToken = localStorage.getItem('refreshToken');
            if (!refreshToken) {
              throw new Error('No refresh token');
            }

            const response = await axios.post(
              `${API_BASE_URL}/api/v1/auth/refresh`,
              { refresh_token: refreshToken }
            );

            const { access_token, user } = response.data;
            
            useAuthStore.getState().setAccessToken(access_token);
            if (user) {
              useAuthStore.getState().setUser(user);
            }

            originalRequest.headers.Authorization = `Bearer ${access_token}`;
            return this.axiosInstance(originalRequest);
          } catch (refreshError) {
            // Refresh failed - logout user
            useAuthStore.getState().logout();
            if (shouldShowToast('Session expired. Please login again.')) {
              toast.error('Session expired. Please login again.');
            }
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }

        const message = getAuthErrorMessage(error);
        if (shouldShowToast(message)) {
          toast.error(message);
        }

        return Promise.reject(error);
      }
    );
  }

  async login(credentials: LoginRequest): Promise<AuthToken> {
    const response = await this.axiosInstance.post<AuthToken>(
      '/api/v1/auth/login',
      credentials
    );
    return response.data;
  }

  async refresh(refreshToken: string): Promise<AuthToken> {
    const response = await this.axiosInstance.post<AuthToken>(
      '/api/v1/auth/refresh',
      { refresh_token: refreshToken }
    );
    return response.data;
  }

  async getMe(): Promise<User> {
    const response = await this.axiosInstance.get<User>(
      '/api/v1/auth/me'
    );
    return response.data;
  }

  async logout(): Promise<void> {
    try {
      await this.axiosInstance.post('/api/v1/auth/logout');
    } catch (error) {
      // Ignore errors on logout
    }
  }

  async changePassword(request: ChangePasswordRequest): Promise<{ message: string }> {
    const response = await this.axiosInstance.post<{ message: string }>(
      '/api/v1/auth/change-password',
      request
    );
    return response.data;
  }
}

export const authApi = new AuthApiClient();
