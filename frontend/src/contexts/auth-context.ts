import * as React from "react";

import type { Permission } from "@/lib/permissions";
import type { User } from "@/types/api";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

export interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  isAuthenticated: boolean;
  authDisabled: boolean;
  login: (identifier: string, password: string) => Promise<User>;
  register: (payload: {
    email: string;
    username: string;
    password: string;
  }) => Promise<User>;
  logout: () => void;
  can: (permission: Permission) => boolean;
}

export const AuthContext = React.createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
