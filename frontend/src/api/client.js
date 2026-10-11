import { API_BASE_URL } from './config';

/**
 * Lightweight, reusable HTTP client for DocumentFlow API
 *
 * @param {string} endpoint - Path relative to base URL (e.g. '/documents')
 * @param {RequestInit} [options={}] - Fetch configuration options
 * @returns {Promise<any>} Parsed response data
 */
export async function apiRequest(endpoint, options = {}) {
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${API_BASE_URL}${normalizedEndpoint}`;

  const headers = {
    Accept: 'application/json',
    ...options.headers,
  };

  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (networkErr) {
    const error = new Error(
      'Unable to connect to the DocumentFlow server. Please check your network connection and ensure the backend service is running.'
    );
    error.status = 0;
    error.isNetworkError = true;
    error.originalError = networkErr;
    throw error;
  }

  if (!response.ok) {
    let errorMessage = `API request failed: ${response.status} ${response.statusText || 'Error'}`;
    let errorDetail = null;

    try {
      const errorJson = await response.json();
      errorDetail = errorJson?.detail;
    } catch {
      // Body is not JSON
    }

    if (errorDetail) {
      if (typeof errorDetail === 'string') {
        // Sanitize raw stack traces and internal exceptions if returned by server error
        const isInternalLeak =
          response.status >= 500 &&
          /Traceback|Error|Exception|psycopg|sqlalchemy|redis|SELECT|INSERT|UPDATE|DELETE|File\s+"|line\s+\d+/i.test(
            errorDetail
          );

        if (isInternalLeak) {
          errorMessage = 'An internal server error occurred while processing the request. Please try again shortly.';
        } else {
          errorMessage = errorDetail;
        }
      } else if (Array.isArray(errorDetail)) {
        // Format FastAPI validation errors into clean user-facing sentences
        const formatted = errorDetail
          .map((item) => {
            if (typeof item === 'object' && item !== null) {
              const loc = Array.isArray(item.loc)
                ? item.loc.filter((part) => part !== 'body').join(' ')
                : '';
              const msg = item.msg || 'Invalid value';
              return loc ? `${loc}: ${msg}` : msg;
            }
            return String(item);
          })
          .filter(Boolean);
        errorMessage = formatted.length > 0 ? formatted.join('. ') : 'Validation error occurred.';
      } else if (typeof errorDetail === 'object') {
        errorMessage = errorDetail.message || errorDetail.msg || JSON.stringify(errorDetail);
      }
    } else {
      // Meaningful defaults based on status code
      if (response.status === 404) {
        errorMessage = 'The requested document or resource was not found.';
      } else if (response.status >= 500) {
        errorMessage = 'An internal server error occurred. Please try again shortly.';
      }
    }

    const error = new Error(errorMessage);
    error.status = response.status;
    error.isNotFound = response.status === 404;
    error.isServerError = response.status >= 500;
    throw error;
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

/**
 * DocumentFlow API methods
 */
export const api = {
  /**
   * Health check endpoint
   */
  getHealth: () => apiRequest('/health'),

  /**
   * Retrieve paginated documents list
   */
  listDocuments: (limit = 20, offset = 0) =>
    apiRequest(`/documents?limit=${limit}&offset=${offset}`),

  /**
   * Retrieve document by UUID
   */
  getDocument: (id) => apiRequest(`/documents/${id}`),

  /**
   * Retry failed document processing job
   */
  retryJob: (id) =>
    apiRequest(`/documents/${id}/retry`, {
      method: 'POST',
    }),

  /**
   * Upload a new document file via multipart/form-data
   * @param {File} file
   */
  uploadDocument: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiRequest('/documents', {
      method: 'POST',
      body: formData,
    });
  },
};

