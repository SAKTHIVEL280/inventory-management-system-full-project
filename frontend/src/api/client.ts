import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';
import Cookies from 'js-cookie';
import { useAuthStore } from '../store/auth';
import { toast } from 'sonner';

axios.defaults.withCredentials = true;

const defaultApiBaseUrl =
  typeof window !== 'undefined'
    ? (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? `${window.location.protocol}//${window.location.hostname}:8001`
        : '')
    : 'http://localhost:8001';

const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl;

const API_BASE_URL = (() => {
  const trimmed = String(rawApiBaseUrl || '').replace(/\/+$/, '');
  if (!trimmed) {
    return '';
  }

  // Endpoints in this app already include '/api/v2/...'.
  // For any relative base like '/api' or '/api/v2', use same-origin empty base.
  if (trimmed.startsWith('/')) {
    return '';
  }

  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    try {
      const url = new URL(trimmed);
      return url.origin;
    } catch {
      const noApiV2 = trimmed.replace(/\/api\/v2$/i, '');
      return noApiV2.replace(/\/api$/i, '');
    }
  }

  return trimmed;
})();

const AUTH_REFRESH_URL = API_BASE_URL.startsWith('http')
  ? `${API_BASE_URL}/api/v2/auth/refresh`
  : '/api/v2/auth/refresh';

const ACCESS_TOKEN_COOKIE_NAMES = ['accessToken', 'access_token'];
const CSRF_COOKIE_NAME = 'csrf_token';
const CSRF_HEADER_NAME = 'X-CSRF-Token';
const MUTATING_METHODS = new Set(['post', 'put', 'patch', 'delete']);

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

interface RetryRequestConfig extends InternalAxiosRequestConfig {
  skipErrorToast?: boolean;
  _retry?: boolean;
}

export interface ApiRequestConfig extends AxiosRequestConfig {
  skipErrorToast?: boolean;
}

const getAccessTokenFromCookie = (): string | null => {
  for (const cookieName of ACCESS_TOKEN_COOKIE_NAMES) {
    const token = Cookies.get(cookieName);
    if (token) {
      return token;
    }
  }
  return null;
};

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
  private readonly refreshClient: AxiosInstance;

  constructor() {
    this.instance = axios.create({
      baseURL: API_BASE_URL,
      withCredentials: true,
      timeout: 15000,
    });

    this.refreshClient = axios.create({
      baseURL: API_BASE_URL,
      withCredentials: true,
      timeout: 15000,
    });

    this.instance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
      const accessToken = getAccessTokenFromCookie();
      if (accessToken) {
        const headers = config.headers || {};
        config.headers = headers;
        if (typeof (headers as { set?: (k: string, v: string) => void }).set === 'function') {
          (headers as { set: (k: string, v: string) => void }).set('Authorization', `Bearer ${accessToken}`);
        } else if (!(headers as Record<string, string>).Authorization) {
          (headers as Record<string, string>).Authorization = `Bearer ${accessToken}`;
        }
      }

      const method = String(config.method || 'get').toLowerCase();
      if (MUTATING_METHODS.has(method)) {
        const csrfToken = Cookies.get(CSRF_COOKIE_NAME);
        if (csrfToken) {
          const headers = config.headers || {};
          config.headers = headers;
          if (typeof (headers as { set?: (k: string, v: string) => void }).set === 'function') {
            (headers as { set: (k: string, v: string) => void }).set(CSRF_HEADER_NAME, csrfToken);
          } else {
            (headers as Record<string, string>)[CSRF_HEADER_NAME] = csrfToken;
          }
        }
      }
      return config;
    });

    this.instance.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = (error.config || {}) as RetryRequestConfig;
        const requestPath = String(originalRequest.url || '');
        const isLoginRequest = requestPath.includes('/api/v2/auth/login');
        const isRefreshRequest = requestPath.includes('/api/v2/auth/refresh');

        if (error.response?.status === 401 && !originalRequest._retry && !isLoginRequest && !isRefreshRequest) {
          originalRequest._retry = true;

          try {
            const refreshResponse = await this.refreshClient.post(AUTH_REFRESH_URL);
            const { user } = refreshResponse.data || {};

            if (user) {
              useAuthStore.getState().setUser(user);
            }
            useAuthStore.getState().setAuthenticated(true);

            return this.instance(originalRequest);
          } catch (_refreshError) {
            useAuthStore.getState().logout();
            if (!originalRequest.skipErrorToast && shouldShowToast('Session expired. Please login again.')) {
              toast.error('Session expired. Please login again.');
            }
            return Promise.reject(_refreshError);
          }
        }

        const requestConfig = (error?.config || {}) as RetryRequestConfig;
        if (!requestConfig.skipErrorToast) {
          const message = normalizeApiErrorMessage(error);
          if (shouldShowToast(message)) {
            toast.error(message);
          }
        }

        return Promise.reject(error);
      }
    );
  }
}

export const apiClient = new ApiClient().instance;

