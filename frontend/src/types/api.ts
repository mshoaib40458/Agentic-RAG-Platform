export type UserRole = "admin" | "document_manager" | "user" | "evaluator";

export type DocumentStatus = "queued" | "processing" | "indexed" | "failed";

export type QueryStatus = "pending" | "processing" | "completed" | "failed";

export type VerificationStatus =
  | "supported"
  | "partially_supported"
  | "unsupported"
  | "skipped";

export type EvaluationStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed";

export interface User {
  id: string;
  email: string;
  username: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface UserUpdate {
  role?: UserRole;
  is_active?: boolean;
}

export interface Token {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  content_type: string | null;
  size_bytes: number;
  owner_id: string;
  collection: string;
  category: string | null;
  status: DocumentStatus;
  error_message: string | null;
  page_count: number | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export type DocumentRecord = Document;

export interface DocumentStats {
  total: number;
  indexed: number;
  processing: number;
  queued: number;
  failed: number;
  total_chunks: number;
}

export interface Citation {
  document_id: string;
  document_name: string;
  chunk_id: string;
  page: number | null;
  snippet: string;
  score: number;
}

export type EvidenceItem = Citation;

export interface Answer {
  id: string;
  content: string;
  model: string;
  verification_status: VerificationStatus;
  citations: Citation[];
  used_evidence: EvidenceItem[];
  prompt_tokens: number | null;
  completion_tokens: number | null;
}

export interface QueryFilters {
  document_ids?: string[] | null;
  category?: string | null;
  collection?: string | null;
}

export interface Query {
  id: string;
  question: string;
  filters: Record<string, unknown>;
  status: QueryStatus;
  intent: string | null;
  latency_ms: number | null;
  stage_timings: Record<string, unknown>;
  error_message: string | null;
  conversation_id: string | null;
  created_at: string;
  answer: Answer | null;
}

export interface QueryRequest {
  question: string;
  filters?: QueryFilters | null;
  top_k?: number | null;
  stream?: boolean;
  conversation_id?: string | null;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  turn_count: number;
}

export interface ConversationDetail {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  turns: Query[];
}

export interface Feedback {
  id: string;
  query_id: string;
  user_id: string;
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface Evaluation {
  id: string;
  dataset_version: string;
  dataset_path: string;
  config: Record<string, unknown>;
  status: EvaluationStatus;
  metrics: Record<string, number>;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface Health {
  status: string;
  version: string;
  environment: string;
  database: string;
  vector_store?: string;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}
