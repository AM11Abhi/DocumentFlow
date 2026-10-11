/**
 * API configuration module
 * Resolves API base URL from VITE_API_BASE_URL with sensible local fallback.
 */
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
).replace(/\/+$/, '');
