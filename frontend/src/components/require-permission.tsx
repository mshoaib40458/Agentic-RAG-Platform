import { Navigate } from "react-router-dom";

import { useAuth } from "@/contexts/auth-context";
import type { Permission } from "@/lib/permissions";

export function RequirePermission({
  permission,
  children,
}: {
  permission: Permission;
  children: React.ReactNode;
}) {
  const { can } = useAuth();
  if (!can(permission)) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}
