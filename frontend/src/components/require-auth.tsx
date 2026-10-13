import { Loader2 } from "lucide-react";
import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "@/contexts/auth-context";

function FullPageLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30">
      <div className="flex items-center gap-3 text-muted-foreground">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
        </span>
        <span className="text-sm">Loading your workspace…</span>
      </div>
    </div>
  );
}

export function RequireAuth() {
  const { status } = useAuth();

  if (status === "loading") {
    return <FullPageLoader />;
  }
  if (status === "anonymous") {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}
