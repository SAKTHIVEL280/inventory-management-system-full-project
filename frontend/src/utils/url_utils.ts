/**
 * Utility for handling backend URLs.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Prefixes a relative static asset path with the backend URL.
 * @param path Relative path from backend root (e.g., '/static/logo.png')
 * @returns Full absolute URL string
 */
export const getStaticUrl = (path: string | null | undefined): string | null => {
  if (!path) return null;
  if (path.startsWith('http')) return path;
  
  // Clean plural slashes
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${cleanPath}`;
};
