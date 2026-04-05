import axios, { AxiosError, AxiosInstance } from 'axios';
import { useAuthStore } from '../store/auth';
import { toast } from 'sonner';

const defaultApiBaseUrl =
  typeof window !== 'undefined'
    ? (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? `${window.location.protocol}//${window.location.hostname}:8001`
        : '/api')
    : 'http://localhost:8001';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl;

type ApiErrorDetail =
  | string
  | {
      message?: string;
      error?: string;
      code?: string;
    }
  | Array<{
      msg?: string;
      message?: string;
    }>;

const errorToastHistory = new Map<string, number>();

interface ApiErrorResponse {
  detail?: ApiErrorDetail;
}

const normalizeApiErrorMessage = (error: unknown): string => {
  const axiosError = error as AxiosError<ApiErrorResponse>;

  if (!axiosError?.response) {
    return 'Cannot reach server. Check internet/CORS/backend status and host (localhost vs 127.0.0.1).';
  }

  const status = axiosError.response.status;
  const detail = axiosError.response.data?.detail;
  const fallbackByStatus: Record<number, string> = {
    400: 'Invalid input. Please check the entered values.',
    401: 'Session expired. Please login again.',
    403: 'You do not have permission to perform this action.',
    404: 'Requested resource was not found.',
    409: 'This action conflicts with existing data.',
    422: 'Some fields are invalid. Please correct and try again.',
  };

  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((d) => d?.msg || d?.message)
      .filter((m): m is string => Boolean(m && m.trim()));
    if (messages.length > 0) {
      return messages.join(', ');
    }
  }

  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    if (typeof detail.message === 'string' && detail.message.trim()) {
      return detail.message;
    }
    if (typeof detail.error === 'string' && detail.error.trim()) {
      return detail.error;
    }
  }

  if (status >= 500) {
    return 'Server error occurred. Please retry. If it continues, contact support.';
  }

  return fallbackByStatus[status] || 'Request failed. Please try again.';
};

const shouldShowToast = (message: string): boolean => {
  const now = Date.now();
  const last = errorToastHistory.get(message) || 0;
  // Prevent toast spam for repeated parallel failures
  if (now - last < 1500) {
    return false;
  }
  errorToastHistory.set(message, now);
  return true;
};

class ApiClient {
  public readonly instance: AxiosInstance;

  constructor() {
    this.instance = axios.create({
      baseURL: API_BASE_URL,
    });

    this.instance.interceptors.request.use((config) => {
      const token = localStorage.getItem('accessToken');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    this.instance.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest?._retry) {
          originalRequest._retry = true;
          try {
            const refreshToken = localStorage.getItem('refreshToken');
            if (!refreshToken) {
              throw new Error('No refresh token');
            }

            const refreshResponse = await axios.post(
              `${API_BASE_URL}/api/v1/auth/refresh`,
              { refresh_token: refreshToken }
            );

            const { access_token, user } = refreshResponse.data;
            useAuthStore.getState().setAccessToken(access_token);
            if (user) {
              useAuthStore.getState().setUser(user);
            }

            originalRequest.headers.Authorization = `Bearer ${access_token}`;
            return this.instance(originalRequest);
          } catch (_refreshError) {
            useAuthStore.getState().logout();
            if (shouldShowToast('Session expired. Please login again.')) {
              toast.error('Session expired. Please login again.');
            }
            window.location.href = '/login';
          }
        }

        // Global user-facing error message for all API failures.
        // Pages can still show inline form errors; this ensures errors never stay console-only.
        const message = normalizeApiErrorMessage(error);
        if (shouldShowToast(message)) {
          toast.error(message);
        }

        return Promise.reject(error);
      }
    );
  }
}

export const apiClient = new ApiClient().instance;
