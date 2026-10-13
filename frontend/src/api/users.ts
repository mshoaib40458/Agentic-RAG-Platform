import { api } from "@/lib/api-client";
import type { Page, User, UserRole } from "@/types/api";

export interface ListUsersParams {
  limit?: number;
  offset?: number;
}

export async function listUsers(
  params: ListUsersParams = {},
): Promise<Page<User>> {
  const { data } = await api.get<Page<User>>("/users", { params });
  return data;
}

export interface UpdateUserPayload {
  role?: UserRole;
  is_active?: boolean;
}

export async function updateUser(
  userId: string,
  payload: UpdateUserPayload,
): Promise<User> {
  const { data } = await api.patch<User>(`/users/${userId}`, payload);
  return data;
}
