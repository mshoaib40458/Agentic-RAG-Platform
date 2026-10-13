import type { UserRole } from "@/types/api";

export const PERMISSIONS = [
  "documents:read",
  "documents:write",
  "documents:delete",
  "query:execute",
  "evaluations:run",
  "users:manage",
] as const;

export type Permission = (typeof PERMISSIONS)[number];

const ROLE_PERMISSIONS: Record<UserRole, readonly Permission[]> = {
  admin: PERMISSIONS,
  document_manager: [
    "documents:read",
    "documents:write",
    "documents:delete",
    "query:execute",
  ],
  user: ["documents:read", "query:execute"],
  evaluator: ["documents:read", "query:execute", "evaluations:run"],
};

export function hasPermission(
  role: UserRole | null | undefined,
  permission: Permission,
): boolean {
  if (!role) return false;
  return ROLE_PERMISSIONS[role]?.includes(permission) ?? false;
}
