import { api } from "@/lib/api-client";
import type { Token, User, UserRole } from "@/types/api";

export interface RegisterPayload {
  email: string;
  username: string;
  password: string;
  role?: UserRole;
}

export async function register(payload: RegisterPayload): Promise<User> {
  const { data } = await api.post<User>("/auth/register", payload);
  return data;
}

export async function login(
  username: string,
  password: string,
): Promise<Token> {
  const { data } = await api.post<Token>("/auth/login", {
    username,
    password,
  });
  return data;
}

export async function fetchMe(): Promise<User> {
  const { data } = await api.get<User>("/auth/me");
  return data;
}

export interface AuthConfig {
  auth_disabled: boolean;
}

export async function fetchAuthConfig(): Promise<AuthConfig> {
  const { data } = await api.get<AuthConfig>("/auth/config");
  return data;
}
