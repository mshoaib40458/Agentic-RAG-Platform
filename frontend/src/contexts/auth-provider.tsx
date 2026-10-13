import * as React from "react";

import {
  fetchAuthConfig,
  fetchMe,
  login as loginRequest,
  register as registerRequest,
} from "@/api/auth";
import {
  AuthContext,
  type AuthContextValue,
  type AuthStatus,
} from "@/contexts/auth-context";
import { hasPermission, type Permission } from "@/lib/permissions";
import { tokenStore } from "@/lib/token-store";
import type { User } from "@/types/api";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<User | null>(null);
  const [status, setStatus] = React.useState<AuthStatus>("loading");
  const [authDisabled, setAuthDisabled] = React.useState(false);

  const clearSession = React.useCallback(() => {
    tokenStore.clear();
    setUser(null);
    setStatus("anonymous");
  }, []);

  React.useEffect(() => {
    let active = true;

    const bootstrap = async () => {
      // Always probe /auth/me: when the backend has auth disabled it returns
      // the bootstrap admin without a token, so the app opens straight up.
      try {
        const me = await fetchMe();
        if (!active) return;
        setUser(me);
        setStatus("authenticated");
      } catch {
        if (active) clearSession();
      }
    };

    void bootstrap();
    return () => {
      active = false;
    };
  }, [clearSession]);

  React.useEffect(() => {
    let active = true;
    fetchAuthConfig()
      .then((config) => {
        if (active) setAuthDisabled(config.auth_disabled);
      })
      .catch(() => {
        /* older backend without /auth/config — keep auth enforced */
      });
    return () => {
      active = false;
    };
  }, []);

  React.useEffect(() => {
    window.addEventListener("auth:unauthorized", clearSession);
    return () => window.removeEventListener("auth:unauthorized", clearSession);
  }, [clearSession]);

  const persistSession = React.useCallback(
    async (accessToken: string, refreshToken: string) => {
      tokenStore.set({ access_token: accessToken, refresh_token: refreshToken });
      const me = await fetchMe();
      setUser(me);
      setStatus("authenticated");
      return me;
    },
    [],
  );

  const login = React.useCallback(
    async (identifier: string, password: string) => {
      const tokens = await loginRequest(identifier, password);
      return persistSession(tokens.access_token, tokens.refresh_token);
    },
    [persistSession],
  );

  const register = React.useCallback(
    async (payload: { email: string; username: string; password: string }) => {
      await registerRequest(payload);
      const tokens = await loginRequest(payload.username, payload.password);
      return persistSession(tokens.access_token, tokens.refresh_token);
    },
    [persistSession],
  );

  const value = React.useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      isAuthenticated: status === "authenticated",
      authDisabled,
      login,
      register,
      logout: clearSession,
      can: (permission: Permission) => hasPermission(user?.role, permission),
    }),
    [user, status, authDisabled, login, register, clearSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
