import { api } from "@/lib/api-client";
import type { Health } from "@/types/api";

export async function getHealth(): Promise<Health> {
  const { data } = await api.get<Health>("/health");
  return data;
}
