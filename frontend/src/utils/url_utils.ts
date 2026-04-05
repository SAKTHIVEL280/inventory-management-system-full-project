/**
 * Utility for handling backend URLs.
 */

const defaultApiBaseUrl =
  typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:8001`
    : 'http://localhost:8001';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl;

const getBackendOrigin = (): string => {
  // Absolute API URLs: use their origin (strip any /api/... path suffix).
  if (API_BASE_URL.startsWith('http://') || API_BASE_URL.startsWith('https://')) {
    try {
      return new URL(API_BASE_URL).origin;
    } catch {
      return API_BASE_URL.replace(/\/+$/, '');
    }
  }

  // Relative API URLs (e.g. /api/v1): serve static files from current origin.
  if (typeof window !== 'undefined') {
    return window.location.origin;
  }

  return 'http://localhost:8001';
};

/**
 * Prefixes a relative static asset path with the backend URL.
 * @param path Relative path from backend root (e.g., '/static/logo.png')
 * @returns Full absolute URL string
 */
export const getStaticUrl = (path: string | null | undefined): string | null => {
  if (!path) return null;
  if (path.startsWith('http')) return path;
  
  // Clean path slashes
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${getBackendOrigin()}${cleanPath}`;
};
