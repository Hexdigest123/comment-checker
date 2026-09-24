export interface ApiError {
  detail: string;
  status_code: number;
}

export interface User {
  id: string;
  username: string;
  name: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export type CommentStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'waiting';

export interface Comment {
  id: string;
  text: string;
  original_author: string | null;
  original_author_url: string | null;
  source_url: string | null;
  source_platform: string | null;
  context: string | null;
  user_id: string;
  status: CommentStatus;
  priority: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  processed_at?: string | null;
  classifications?: Classification[];
}

export interface CommentSearchResult {
  id: string;
  text: string;
  original_author: string | null;
  source_url: string | null;
  source_platform: string | null;
  status: CommentStatus;
  similarity: number;
  created_at: string;
}

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
  category: ClassificationCategory | null;
  severity: ClassificationSeverity | null;
  confidence: number;
  harmful_score: number;
  details: Record<string, unknown>;
  created_at: string;
}

export interface PageResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface CSVUploadResponse {
  message: string;
  batch_id: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  processing: boolean;
}

// Cluster graph (entity + relations)
export interface GraphNode {
  id: string;
  name: string;
  type: 'cluster' | 'account';
  platform?: string;
  cluster_type?: string;
  comment_count?: number;
  toxicity_score?: number;
  color?: string | null;
  index: number;
}

export interface GraphLink {
  source: number;
  target: number;
  type: 'connection' | 'belongs_to';
  connection_type?: string;
  confidence?: number;
  status?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

// AI assistant
export interface AIToolCall {
  tool: string;
  input?: Record<string, unknown> | null;
  output?: Record<string, unknown> | null;
}

export interface AIChatMessage {
  role: 'user' | 'assistant';
  content: string;
  tool_calls?: AIToolCall[] | null;
  model?: string | null;
  tokens?: number | null;
  latency_ms?: number | null;
}

export interface AIChatResponse {
  response: string;
  tool_used: string | null;
  tool_calls: AIToolCall[];
  conversation_id: string | null;
  session_id: string | null;
  model: string | null;
  tokens: number | null;
  latency_ms: number | null;
}

// Import via ExportComments
export interface ImportStatus {
  configured: boolean;
  platforms: string[];
}
