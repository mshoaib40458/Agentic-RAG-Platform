import * as React from "react";
import { Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { ErrorBoundary } from "@/components/error-boundary";
import { RequireAuth } from "@/components/require-auth";
import { RequirePermission } from "@/components/require-permission";
import { Spinner } from "@/components/spinner";

const DashboardPage = React.lazy(() =>
  import("@/pages/dashboard").then((m) => ({ default: m.DashboardPage })),
);
const AskPage = React.lazy(() =>
  import("@/pages/ask").then((m) => ({ default: m.AskPage })),
);
const DocumentsPage = React.lazy(() =>
  import("@/pages/documents").then((m) => ({ default: m.DocumentsPage })),
);
const EvaluationsPage = React.lazy(() =>
  import("@/pages/evaluations").then((m) => ({ default: m.EvaluationsPage })),
);
const UsersPage = React.lazy(() =>
  import("@/pages/users").then((m) => ({ default: m.UsersPage })),
);
const LoginPage = React.lazy(() =>
  import("@/pages/login").then((m) => ({ default: m.LoginPage })),
);
const RegisterPage = React.lazy(() =>
  import("@/pages/register").then((m) => ({ default: m.RegisterPage })),
);
const NotFoundPage = React.lazy(() =>
  import("@/pages/not-found").then((m) => ({ default: m.NotFoundPage })),
);

function RouteFallback() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center text-muted-foreground">
      <Spinner className="h-6 w-6" />
    </div>
  );
}

export function App() {
  return (
    <ErrorBoundary>
      <React.Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route element={<RequireAuth />}>
            <Route element={<AppShell />}>
              <Route index element={<DashboardPage />} />
              <Route
                path="/ask"
                element={
                  <RequirePermission permission="query:execute">
                    <AskPage />
                  </RequirePermission>
                }
              />
              <Route
                path="/documents"
                element={
                  <RequirePermission permission="documents:read">
                    <DocumentsPage />
                  </RequirePermission>
                }
              />
              <Route
                path="/evaluations"
                element={
                  <RequirePermission permission="evaluations:run">
                    <EvaluationsPage />
                  </RequirePermission>
                }
              />
              <Route
                path="/users"
                element={
                  <RequirePermission permission="users:manage">
                    <UsersPage />
                  </RequirePermission>
                }
              />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Route>
        </Routes>
      </React.Suspense>
    </ErrorBoundary>
  );
}
