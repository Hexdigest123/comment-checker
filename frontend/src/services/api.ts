import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import type { ApiError } from '../types';

// Create API client
const api: AxiosInstance = axios.create({
  baseURL: import.meta.env.PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle errors and refresh tokens
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Handle 401 Unauthorized - try to refresh token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) {
          throw new Error('No refresh token');
        }

        const response = await axios.post(
          `${import.meta.env.PUBLIC_API_URL || 'http://localhost:8000'}/auth/refresh`,
          { refresh_token: refreshToken },
          { headers: { 'Content-Type': 'application/json' } }
        );

        const { access_token } = response.data;
        localStorage.setItem('access_token', access_token);

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
        }

        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed - logout user
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    // Transform error response
    const apiError: ApiError = {
      detail: error.response?.data?.detail || error.message || 'An unexpected error occurred',
      status_code: error.response?.status || 500,
    };

    return Promise.reject(apiError);
  }
);

// Auth API
export const authApi = {
  login: (data: { email: string; password: string }) =>
    api.post<{ access_token: string; token_type: string; user: unknown }>('/auth/login', data),

  refresh: (refreshToken: string) =>
    api.post<{ access_token: string; token_type: string }>('/auth/refresh', { refresh_token: refreshToken }),

  logout: () => api.post('/auth/logout'),

  me: () => api.get<{ user: unknown }>('/auth/me'),
};

// User API
export const userApi = {
  list: (params?: { page?: number; page_size?: number; search?: string }) =>
    api.get('/users', { params }),

  get: (id: string) => api.get(`/users/${id}`),

  create: (data: unknown) => api.post('/users', data),

  update: (id: string, data: unknown) => api.put(`/users/${id}`, data),

  delete: (id: string) => api.delete(`/users/${id}`),
};

// Comment API
export const commentApi = {
  list: (params?: { page?: number; page_size?: number; search?: string; status?: string; sort_by?: string; sort_order?: string }) =>
    api.get('/comments', { params }),

  get: (id: string) => api.get(`/comments/${id}`),

  create: (data: unknown) => api.post('/comments', data),

  update: (id: string, data: unknown) => api.put(`/comments/${id}`, data),

  delete: (id: string) => api.delete(`/comments/${id}`),

  uploadCSV: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/comments/upload-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  classify: (id: string) => api.post(`/comments/${id}/classify`),

  reclassify: (id: string) => api.post(`/comments/${id}/reclassify`),
};

// Classification API
export const classificationApi = {
  list: (params?: { page?: number; page_size?: number; comment_id?: string; backend?: string; category?: string }) =>
    api.get('/classifications', { params }),

  get: (id: string) => api.get(`/classifications/${id}`),

  stats: () => api.get('/classifications/stats'),
};

// Dashboard API
export const dashboardApi = {
  stats: (params?: { start_date?: string; end_date?: string }) =>
    api.get('/dashboard/stats', { params }),

  statusDistribution: (params?: { start_date?: string; end_date?: string }) =>
    api.get('/dashboard/status-distribution', { params }),

  categoryDistribution: (params?: { start_date?: string; end_date?: string }) =>
    api.get('/dashboard/category-distribution', { params }),
};

// Invite API
export const inviteApi = {
  list: () => api.get('/invites'),

  create: (email: string) => api.post('/invites', { email }),

  get: (token: string) => api.get(`/invites/${token}`),

  use: (token: string, data: { name: string; password: string }) =>
    api.post(`/invites/${token}/use`, data),

  delete: (token: string) => api.delete(`/invites/${token}`),
};

// Password Reset API
export const passwordResetApi = {
  request: (email: string) => api.post('/password-reset/request', { email }),

  confirm: (token: string, password: string) =>
    api.post('/password-reset/confirm', { token, password }),
};

// Health check
export const healthApi = {
  check: () => api.get('/health'),
};

export default api;
