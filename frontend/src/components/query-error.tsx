import { AlertTriangle, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";

interface QueryErrorProps {
  error: unknown;
  onRetry?: () => void;
  title?: string;
  className?: string;
}

export function QueryError({
  error,
  onRetry,
  title = "Couldn't load this data",
  className,
}: QueryErrorProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed bg-card/50 px-6 py-10 text-center",
        className,
      )}
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <AlertTriangle className="h-5 w-5" />
      </span>
      <div className="space-y-1">
        <p className="text-sm font-medium">{title}</p>
        <p className="max-w-sm text-sm text-muted-foreground">
          {getApiError(error).message}
        </p>
      </div>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCcw className="mr-2 h-4 w-4" />
          Retry
        </Button>
      ) : null}
    </div>
  );
}
