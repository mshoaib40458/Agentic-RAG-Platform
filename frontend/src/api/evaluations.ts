import { api } from "@/lib/api-client";
import type { Evaluation, Page } from "@/types/api";

export interface CreateEvaluationPayload {
  dataset_version: string;
  dataset_path?: string;
  config?: Record<string, unknown>;
}

export async function createEvaluation(
  payload: CreateEvaluationPayload,
): Promise<Evaluation> {
  const { data } = await api.post<Evaluation>("/evaluations", payload);
  return data;
}

export interface ListEvaluationsParams {
  limit?: number;
  offset?: number;
}

export async function listEvaluations(
  params: ListEvaluationsParams = {},
): Promise<Page<Evaluation>> {
  const { data } = await api.get<Page<Evaluation>>("/evaluations", { params });
  return data;
}

export async function getEvaluation(runId: string): Promise<Evaluation> {
  const { data } = await api.get<Evaluation>(`/evaluations/${runId}`);
  return data;
}
