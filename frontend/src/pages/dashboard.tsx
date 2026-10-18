import { useQuery } from "@tanstack/react-query";
import { Activity, Database, FileText, Layers, ServerCog } from "lucide-react";

import { getDocumentStats } from "@/api/documents";
import { getHealth } from "@/api/health";
import { PageHeader } from "@/components/page-header";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/contexts/auth-context";
import { formatNumber, titleCase } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

function StatCard({
  label,
  value,
  icon: Icon,
  hint,
}: {
  label: string;
  value: string;
  icon: typeof FileText;
  hint?: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold tracking-tight">{value}</p>
          {hint ? (
            <p className="truncate text-xs text-muted-foreground">{hint}</p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

export function DashboardPage() {
  const { user } = useAuth();

  const stats = useQuery({
    queryKey: queryKeys.documentStats,
    queryFn: getDocumentStats,
  });

  const health = useQuery({
    queryKey: queryKeys.health,
    queryFn: getHealth,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome${user ? `, ${user.username}` : ""}`}
        description="Your workspace at a glance."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.isLoading
          ? Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-[104px] rounded-xl" />
            ))
          : null}
        {stats.data ? (
          <>
            <StatCard
              label="Documents"
              value={formatNumber(stats.data.total)}
              icon={FileText}
              hint={`${formatNumber(stats.data.indexed)} indexed`}
            />
            <StatCard
              label="Chunks"
              value={formatNumber(stats.data.total_chunks)}
              icon={Layers}
              hint="Searchable passages"
            />
            <StatCard
              label="Processing"
              value={formatNumber(
                stats.data.processing + stats.data.queued,
              )}
              icon={Activity}
              hint="Queued or processing"
            />
            <StatCard
              label="Failed"
              value={formatNumber(stats.data.failed)}
              icon={ServerCog}
              hint="Failed ingestion"
            />
          </>
        ) : null}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ServerCog className="h-4 w-4 text-muted-foreground" /> System status
            </CardTitle>
          </CardHeader>
          <CardContent>
            {health.isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, index) => (
                  <Skeleton key={index} className="h-10 rounded-lg" />
                ))}
              </div>
            ) : null}
            {health.data ? (
              <dl className="space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <dt className="flex items-center gap-2 text-muted-foreground">
                    <Activity className="h-4 w-4" /> Status
                  </dt>
                  <dd className="font-medium">
                    {titleCase(health.data.status)}
                  </dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="flex items-center gap-2 text-muted-foreground">
                    <Database className="h-4 w-4" /> Database
                  </dt>
                  <dd className="font-medium">
                    {titleCase(health.data.database)}
                  </dd>
                </div>
                {health.data.vector_store ? (
                  <div className="flex items-center justify-between">
                    <dt className="flex items-center gap-2 text-muted-foreground">
                      <Layers className="h-4 w-4" /> Vector store
                    </dt>
                    <dd className="font-medium">
                      {titleCase(health.data.vector_store)}
                    </dd>
                  </div>
                ) : null}
                <div className="flex items-center justify-between">
                  <dt className="flex items-center gap-2 text-muted-foreground">
                    <ServerCog className="h-4 w-4" /> Version
                  </dt>
                  <dd className="font-medium">{health.data.version}</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="flex items-center gap-2 text-muted-foreground">
                    <Layers className="h-4 w-4" /> Environment
                  </dt>
                  <dd className="font-medium">
                    {titleCase(health.data.environment)}
                  </dd>
                </div>
              </dl>
            ) : null}
            {health.isError ? (
              <p className="text-sm text-destructive">
                Backend is unreachable. Start the API server and refresh.
              </p>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
