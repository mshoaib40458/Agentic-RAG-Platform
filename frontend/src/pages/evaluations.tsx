import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, Plus } from "lucide-react";
import { toast } from "sonner";

import {
  createEvaluation,
  listEvaluations,
  type CreateEvaluationPayload,
} from "@/api/evaluations";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { QueryError } from "@/components/query-error";
import { Spinner } from "@/components/spinner";
import { EvaluationStatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/contexts/auth-context";
import { getApiError } from "@/lib/api-client";
import { formatDate } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { Evaluation } from "@/types/api";

const PAGE_SIZE = 10;

export function EvaluationsPage() {
  const { can } = useAuth();
  const [page, setPage] = React.useState(0);
  const [createOpen, setCreateOpen] = React.useState(false);

  const params = { limit: PAGE_SIZE, offset: page * PAGE_SIZE };
  const evaluations = useQuery({
    queryKey: queryKeys.evaluations(params),
    queryFn: () => listEvaluations(params),
    refetchInterval: (query) => {
      const hasPending = query.state.data?.items.some(
        (evaluation) =>
          evaluation.status === "running" || evaluation.status === "pending",
      );
      return hasPending ? 3000 : false;
    },
  });

  const total = evaluations.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const canRun = can("evaluations:run");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Evaluations"
        description="Measure retrieval and answer quality against labelled datasets."
        actions={
          canRun ? (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" />
              New run
            </Button>
          ) : null
        }
      />

      {evaluations.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-28 rounded-xl" />
          ))}
        </div>
      ) : null}

      {evaluations.isError ? (
        <QueryError
          error={evaluations.error}
          onRetry={() => evaluations.refetch()}
        />
      ) : null}

      {evaluations.data && evaluations.data.items.length === 0 ? (
        <EmptyState
          icon={BarChart3}
          title="No evaluation runs yet"
          description={
            canRun
              ? "Start a run to score your pipeline against a dataset."
              : "Evaluation runs will appear here once created."
          }
          action={
            canRun ? (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" />
                New run
              </Button>
            ) : null
          }
        />
      ) : null}

      <div className="grid gap-3">
        {evaluations.data?.items.map((evaluation) => (
          <EvaluationCard key={evaluation.id} evaluation={evaluation} />
        ))}
      </div>

      {total > PAGE_SIZE ? (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Page {page + 1} of {pageCount}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 0}
              onClick={() => setPage((current) => Math.max(0, current - 1))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page + 1 >= pageCount}
              onClick={() => setPage((current) => current + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}

      <CreateEvaluationDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
      />
    </div>
  );
}

function EvaluationCard({ evaluation }: { evaluation: Evaluation }) {
  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <EvaluationStatusBadge status={evaluation.status} />
            <CardTitle className="text-base">
              {evaluation.dataset_version}
            </CardTitle>
          </div>
          <span className="text-xs text-muted-foreground">
            {formatDate(evaluation.created_at)}
          </span>
        </div>
        {evaluation.dataset_path ? (
          <CardDescription className="truncate font-mono text-xs">
            {evaluation.dataset_path}
          </CardDescription>
        ) : null}
      </CardHeader>
      <CardContent>
        {evaluation.error_message ? (
          <p className="text-sm text-destructive">{evaluation.error_message}</p>
        ) : Object.keys(evaluation.metrics).length > 0 ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {Object.entries(evaluation.metrics).map(([key, value]) => (
              <div key={key} className="rounded-lg border bg-muted/30 p-3">
                <p className="truncate text-xs capitalize text-muted-foreground">
                  {key.replace(/_/g, " ")}
                </p>
                <p className="mt-1 text-lg font-semibold tabular-nums">
                  {typeof value === "number" ? value.toFixed(3) : String(value)}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No metrics reported for this run.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function CreateEvaluationDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [datasetVersion, setDatasetVersion] = React.useState("");
  const [datasetPath, setDatasetPath] = React.useState("");

  const mutation = useMutation({
    mutationFn: (payload: CreateEvaluationPayload) =>
      createEvaluation(payload),
    onSuccess: () => {
      toast.success("Evaluation run started");
      queryClient.invalidateQueries({ queryKey: ["evaluations"] });
      setDatasetVersion("");
      setDatasetPath("");
      onOpenChange(false);
    },
    onError: (error) => toast.error(getApiError(error).message),
  });

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!datasetVersion.trim()) {
      toast.error("Dataset version is required.");
      return;
    }
    mutation.mutate({
      dataset_version: datasetVersion.trim(),
      dataset_path: datasetPath.trim() || undefined,
    });
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!mutation.isPending) onOpenChange(next);
      }}
    >
      <DialogContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>New evaluation run</DialogTitle>
            <DialogDescription>
              Provide a labelled dataset to score the pipeline.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="dataset-version">Dataset version</Label>
            <Input
              id="dataset-version"
              value={datasetVersion}
              onChange={(event) => setDatasetVersion(event.target.value)}
              placeholder="e.g. v1"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="dataset-path">Dataset path (optional)</Label>
            <Input
              id="dataset-path"
              value={datasetPath}
              onChange={(event) => setDatasetPath(event.target.value)}
              placeholder="evaluations/golden_v1.jsonl"
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? <Spinner /> : null}
              Start run
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
