import axios from 'axios';

/**
 * Single axios instance for the whole application.
 *
 * Development: VITE_API_BASE_URL (default `/api/v1`, proxied by Vite).
 * Production:  `/api/v1`, proxied by Nginx - never a hardcoded localhost URL.
 */
const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60_000,
});

// Unwrap the standard envelope: { data, message, error }.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(error),
);

export function unwrap(response) {
  return response?.data?.data ?? null;
}

export function unwrapMessage(response) {
  return response?.data?.message ?? '';
}

/** Absolute URL of a path relative to the API base (used by SSE). */
export function apiUrl(path) {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  if (/^https?:\/\//i.test(baseURL)) {
    return `${baseURL.replace(/\/$/, '')}${normalized}`;
  }
  return `${baseURL.replace(/\/$/, '')}${normalized}`;
}
