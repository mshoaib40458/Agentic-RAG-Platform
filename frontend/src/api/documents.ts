import { api } from "@/lib/api-client";
import type { Document, Page } from "@/types/api";
import type { DocumentStats, DocumentStatus } from "@/types/api";

export interface ListDocumentsParams {
  limit?: number;
  offset?: number;
  category?: string;
  collection?: string;
  status_filter?: DocumentStatus;
  search?: string;
}

export async function listDocuments(
  params: ListDocumentsParams = {},
): Promise<Page<Document>> {
  const { data } = await api.get<Page<Document>>("/documents", { params });
  return data;
}

export async function getDocument(documentId: string): Promise<Document> {
  const { data } = await api.get<Document>(`/documents/${documentId}`);
  return data;
}

export async function getDocumentStats(): Promise<DocumentStats> {
  const { data } = await api.get<DocumentStats>("/documents/stats");
  return data;
}

export interface UploadDocumentPayload {
  file: File;
  category?: string;
  collection?: string;
}

export async function uploadDocument(
  payload: UploadDocumentPayload,
): Promise<Document> {
  const form = new FormData();
  form.append("file", payload.file);
  if (payload.category) form.append("category", payload.category);
  form.append("collection", payload.collection || "default");

  const { data } = await api.post<Document>("/documents", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export interface UpdateDocumentPayload {
  category?: string | null;
  collection?: string | null;
}

export async function updateDocument(
  documentId: string,
  payload: UpdateDocumentPayload,
): Promise<Document> {
  const { data } = await api.patch<Document>(
    `/documents/${documentId}`,
    payload,
  );
  return data;
}

export async function deleteDocument(documentId: string): Promise<void> {
  await api.delete(`/documents/${documentId}`);
}
