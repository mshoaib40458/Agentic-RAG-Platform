import { api } from "@/lib/api-client";
import type { Conversation, ConversationDetail, Page } from "@/types/api";

export interface ListConversationsParams {
  limit?: number;
  offset?: number;
}

export async function listConversations(
  params: ListConversationsParams = {},
): Promise<Page<Conversation>> {
  const { data } = await api.get<Page<Conversation>>("/conversations", { params });
  return data;
}

export async function createConversation(
  title?: string,
): Promise<Conversation> {
  const { data } = await api.post<Conversation>("/conversations", { title });
  return data;
}

export async function getConversation(
  conversationId: string,
): Promise<ConversationDetail> {
  const { data } = await api.get<ConversationDetail>(
    `/conversations/${conversationId}`,
  );
  return data;
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await api.delete(`/conversations/${conversationId}`);
}
