import axios, {
  AxiosError,
  type InternalAxiosRequestConfig,
} from "axios";

import { tokenStore } from "@/lib/token-store";
import type { ApiErrorBody, Token } from "@/types/api";

export const API_URL = import.meta.env.VITE_API_URL ?? "/api/v1";

export const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = tokenStore.getAccess();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

type RetriableConfig = InternalAxiosRequestConfig & { _retry?: boolean };

let refreshInFlight: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const refreshToken = tokenStore.getRefresh();
  if (!refreshToken) {
    throw new Error("No refresh token available");
  }
  const { data } = await axios.post<Token>(`${API_URL}/auth/refresh`, {
    refresh_token: refreshToken,
  });
  tokenStore.set(data);
  return data.access_token;
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined;
    const isAuthError = error.response?.status === 401;

    if (isAuthError && config && !config._retry && tokenStore.getRefresh()) {
      config._retry = true;
      try {
        refreshInFlight ??= refreshAccessToken().finally(() => {
          refreshInFlight = null;
        });
        const accessToken = await refreshInFlight;
        config.headers.Authorization = `Bearer ${accessToken}`;
        return api(config);
      } catch {
        tokenStore.clear();
        window.dispatchEvent(new Event("auth:unauthorized"));
      }
    }

    return Promise.reject(error);
  },
);

export function getApiError(error: unknown): ApiErrorBody {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { error?: Partial<ApiErrorBody> }
      | undefined;
    if (data?.error?.message) {
      return {
        code: data.error.code ?? "error",
        message: data.error.message,
        details: data.error.details ?? null,
      };
    }
    if (error.code === "ERR_NETWORK") {
      return {
        code: "network_error",
        message: "Unable to reach the server. Is the backend running?",
      };
    }
    return {
      code: "request_failed",
      message: error.message || "The request failed.",
    };
  }
  if (error instanceof Error) {
    return { code: "error", message: error.message };
  }
  return { code: "error", message: "An unexpected error occurred." };
}

export function isAxiosError(error: unknown): error is AxiosError {
  return axios.isAxiosError(error);
}
