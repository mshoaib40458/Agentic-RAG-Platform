import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { titleCase } from "@/lib/format";
import type {
  DocumentStatus,
  EvaluationStatus,
  QueryStatus,
  VerificationStatus,
} from "@/types/api";

type BadgeVariant =
  | "default"
  | "secondary"
  | "destructive"
  | "outline"
  | "success"
  | "warning"
  | "info";

const DOCUMENT: Record<DocumentStatus, BadgeVariant> = {
  queued: "secondary",
  processing: "info",
  indexed: "success",
  failed: "destructive",
};

const QUERY: Record<QueryStatus, BadgeVariant> = {
  pending: "secondary",
  processing: "info",
  completed: "success",
  failed: "destructive",
};

const VERIFICATION: Record<VerificationStatus, BadgeVariant> = {
  supported: "success",
  partially_supported: "warning",
  unsupported: "destructive",
  skipped: "secondary",
};

const EVALUATION: Record<EvaluationStatus, BadgeVariant> = {
  pending: "secondary",
  running: "info",
  completed: "success",
  failed: "destructive",
};

const DOT: Record<BadgeVariant, string> = {
  default: "bg-primary-foreground",
  secondary: "bg-muted-foreground",
  destructive: "bg-destructive-foreground",
  outline: "bg-foreground",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  info: "bg-blue-500",
};

function StatusBadge({
  variant,
  label,
  className,
}: {
  variant: BadgeVariant;
  label: string;
  className?: string;
}) {
  return (
    <Badge variant={variant} className={cn("gap-1.5", className)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", DOT[variant])} />
      {label}
    </Badge>
  );
}

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <StatusBadge variant={statusVariant(DOCUMENT, status)} label={titleCase(status)} />
  );
}

export function QueryStatusBadge({ status }: { status: QueryStatus }) {
  return (
    <StatusBadge variant={statusVariant(QUERY, status)} label={titleCase(status)} />
  );
}

export function EvaluationStatusBadge({ status }: { status: EvaluationStatus }) {
  return (
    <StatusBadge
      variant={statusVariant(EVALUATION, status)}
      label={titleCase(status)}
    />
  );
}

const VERIFICATION_LABELS: Record<VerificationStatus, string> = {
  supported: "Verified",
  partially_supported: "Partially verified",
  unsupported: "Unverified",
  skipped: "Not checked",
};

export function VerificationBadge({
  status,
}: {
  status: VerificationStatus;
}) {
  return (
    <StatusBadge
      variant={statusVariant(VERIFICATION, status)}
      label={VERIFICATION_LABELS[status] ?? titleCase(status)}
    />
  );
}

function statusVariant<T extends string>(
  map: Record<T, BadgeVariant>,
  key: T,
): BadgeVariant {
  return map[key] ?? "secondary";
}
