import { api } from "@/lib/api-client";
import type { Page, Query, QueryRequest } from "@/types/api";

export async function submitQuery(payload: QueryRequest): Promise<Query> {
  const { data } = await api.post<Query>("/query", payload);
  return data;
}

export interface ListQueriesParams {
  limit?: number;
  offset?: number;
}

export async function listQueries(
  params: ListQueriesParams = {},
): Promise<Page<Query>> {
  const { data } = await api.get<Page<Query>>("/query", { params });
  return data;
}

export async function getQuery(queryId: string): Promise<Query> {
  const { data } = await api.get<Query>(`/query/${queryId}`);
  return data;
}
