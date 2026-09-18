// API Types
export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface ApiError {
  detail: string;
  status_code: number;
}

// User Types
export interface User {
  id: string;
  email: string;
  name: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserCreate {
  email: string;
  name: string;
  password: string;
}

export interface UserUpdate {
  email?: string;
  name?: string;
  password?: string;
}

// Auth Types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface RefreshResponse {
  access_token: string;
  token_type: string;
}

// Token Types
export interface Token {
  id: string;
  token: string;
  user_id: string;
  expires_at: string;
  is_used: boolean;
  created_at: string;
}

// Comment Types
export type CommentStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'waiting';

export interface Comment {
  id: string;
  text: string;
  source_url: string | null;
  user_id: string;
  status: CommentStatus;
  created_at: string;
  updated_at: string;
  user?: User;
  classifications?: Classification[];
}

export interface CommentCreate {
  text: string;
  source_url?: string;
}

export interface CommentUpload {
  file: File;
}

// Classification Types
export type ClassificationBackend = 'typesafe' | 'mistral' | 'combined';
export type ClassificationCategory = 
  | 'hate'
  | 'harassment'
  | 'violence'
  | 'self_harm'
  | 'sexual'
  | 'spam'
  | 'illegal'
  | 'safe';
export type ClassificationSeverity = 'low' | 'medium' | 'high' | 'critical';

export interface Classification {
  id: string;
  comment_id: string;
  backend: ClassificationBackend;
  category: ClassificationCategory;
  severity: ClassificationSeverity;
  confidence: number;
  harmful_score: number;
  details: Record<string, unknown>;
  created_at: string;
}

// Dashboard Types
export interface DashboardStats {
  total_comments: number;
  processed: number;
  processing: number;
  waiting: number;
  failed: number;
  category_distribution: Record<ClassificationCategory, number>;
  backend_distribution: Record<ClassificationBackend, number>;
  recent_comments: Comment[];
}

export interface DateRange {
  start_date: string;
  end_date: string;
}

// Invite Types
export interface InviteToken {
  id: string;
  token: string;
  email: string;
  is_used: boolean;
  expires_at: string;
  created_at: string;
  created_by: string;
}

export interface InviteCreate {
  email: string;
}

// Password Reset Types
export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirm {
  token: string;
  password: string;
}

// Pagination Types
export interface PageParams {
  page: number;
  page_size: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  search?: string;
  filters?: Record<string, string>;
}

export interface PageResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// CSV Types
export interface CSVUploadResponse {
  message: string;
  comments_created: number;
  comments: Comment[];
}

// Notification Types
export interface Notification {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
  created_at: string;
}
