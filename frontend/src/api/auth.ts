/**
 * Auth API Client
 * 
 * Centralized place for all auth-related API calls.
 * No fetch/axios calls in components - all API logic here.
 */

import axios, { AxiosInstance } from 'axios';
import { LoginRequest, AuthToken, ChangePasswordRequest } from '../types';
import { useAuthStore } from '../store/auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
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

  async getMe(): Promise<AuthToken> {
    const response = await this.axiosInstance.get<AuthToken>(
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
