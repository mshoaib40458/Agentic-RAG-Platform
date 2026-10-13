import { api } from "@/lib/api-client";
import type { Feedback } from "@/types/api";

export interface SubmitFeedbackPayload {
  query_id: string;
  rating: number;
  comment?: string;
}

export async function submitFeedback(
  payload: SubmitFeedbackPayload,
): Promise<Feedback> {
  const { data } = await api.post<Feedback>("/feedback", payload);
  return data;
}

export async function listFeedbackForQuery(
  queryId: string,
): Promise<Feedback[]> {
  const { data } = await api.get<Feedback[]>(`/feedback/query/${queryId}`);
  return data;
}
