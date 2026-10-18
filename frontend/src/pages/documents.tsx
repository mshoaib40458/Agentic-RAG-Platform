import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  FileUp,
  MoreHorizontal,
  Pencil,
  RefreshCw,
  Search,
  Trash2,
  Upload,
} from "lucide-react";
import { toast } from "sonner";

import {
  deleteDocument,
  getDocumentStats,
  listDocuments,
  updateDocument,
  uploadDocument,
  type ListDocumentsParams,
} from "@/api/documents";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { QueryError } from "@/components/query-error";
import { Spinner } from "@/components/spinner";
import { DocumentStatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/contexts/auth-context";
import { getApiError } from "@/lib/api-client";
import { formatBytes, formatDate, formatNumber } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { Document, DocumentStatus } from "@/types/api";

const PAGE_SIZE = 10;
const ACCEPTED = ".pdf,.txt,.docx";

type StatusFilter = DocumentStatus | "all";

export function DocumentsPage() {
  const { can } = useAuth();
  const queryClient = useQueryClient();

  const [search, setSearch] = React.useState("");
  const [debouncedSearch, setDebouncedSearch] = React.useState("");
  const [status, setStatus] = React.useState<StatusFilter>("all");
  const [page, setPage] = React.useState(0);
  const [uploadOpen, setUploadOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Document | null>(null);
  const [deleting, setDeleting] = React.useState<Document | null>(null);

  React.useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(0);
    }, 350);
    return () => window.clearTimeout(handle);
  }, [search]);

  const params: ListDocumentsParams = {
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
    search: debouncedSearch || undefined,
    status_filter: status === "all" ? undefined : status,
  };

  const documents = useQuery({
    queryKey: queryKeys.documents(params),
    queryFn: () => listDocuments(params),
    refetchInterval: (query) => {
      const hasPending = query.state.data?.items.some(
        (doc) => doc.status === "queued" || doc.status === "processing",
      );
      return hasPending ? 2500 : false;
    },
  });

  const stats = useQuery({
    queryKey: queryKeys.documentStats,
    queryFn: getDocumentStats,
    refetchInterval: (query) => {
      const data = query.state.data;
      const hasPending = data ? data.processing + data.queued > 0 : false;
      return hasPending ? 2500 : false;
    },
  });

  const canWrite = can("documents:write");
  const canDelete = can("documents:delete");

  const deleteMutation = useMutation({
    mutationFn: (documentId: string) => deleteDocument(documentId),
    onSuccess: () => {
      toast.success("Document deleted");
      if (page > 0 && documents.data?.items.length === 1) {
        setPage((current) => Math.max(0, current - 1));
      }
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      setDeleting(null);
    },
    onError: (error) => toast.error(getApiError(error).message),
  });

  const total = documents.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Documents"
        description="Upload and manage the sources your answers are grounded in."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              aria-label="Refresh"
              onClick={() => {
                documents.refetch();
                stats.refetch();
              }}
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
            {canWrite ? (
              <Button onClick={() => setUploadOpen(true)}>
                <Upload className="h-4 w-4" />
                Upload
              </Button>
            ) : null}
          </div>
        }
      />

      {stats.data ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { label: "Total", value: stats.data.total },
            { label: "Indexed", value: stats.data.indexed },
            {
              label: "Processing",
              value: stats.data.processing + stats.data.queued,
            },
            { label: "Chunks", value: stats.data.total_chunks },
          ].map((item) => (
            <Card key={item.label}>
              <CardContent className="p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  {item.label}
                </p>
                <p className="mt-1 text-xl font-semibold">
                  {formatNumber(item.value)}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by filename…"
            className="pl-9"
          />
        </div>
        <Select
          value={status}
          onValueChange={(value) => {
            setStatus(value as StatusFilter);
            setPage(0);
          }}
        >
          <SelectTrigger className="w-full sm:w-44" aria-label="Filter by status">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="queued">Queued</SelectItem>
            <SelectItem value="processing">Processing</SelectItem>
            <SelectItem value="indexed">Indexed</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardContent className="p-0">
          {documents.isLoading ? (
            <div className="space-y-3 p-4">
              {Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-12 rounded-lg" />
              ))}
            </div>
          ) : null}

          {documents.isError ? (
            <div className="p-4">
              <QueryError
                error={documents.error}
                onRetry={() => documents.refetch()}
              />
            </div>
          ) : null}

          {documents.data && documents.data.items.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead className="hidden md:table-cell">Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="hidden lg:table-cell">Chunks</TableHead>
                  <TableHead className="hidden lg:table-cell">Size</TableHead>
                  <TableHead className="hidden xl:table-cell">Created</TableHead>
                  <TableHead className="w-12 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.data.items.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="max-w-[220px]">
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <span
                          className="truncate font-medium"
                          title={doc.filename}
                        >
                          {doc.filename}
                        </span>
                      </div>
                      {doc.error_message ? (
                        <p className="mt-1 truncate text-xs text-destructive">
                          {doc.error_message}
                        </p>
                      ) : null}
                    </TableCell>
                    <TableCell className="hidden text-xs uppercase text-muted-foreground md:table-cell">
                      {doc.file_type}
                    </TableCell>
                    <TableCell>
                      <DocumentStatusBadge status={doc.status} />
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      {formatNumber(doc.chunk_count)}
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground lg:table-cell">
                      {formatBytes(doc.size_bytes)}
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground xl:table-cell">
                      {formatDate(doc.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="Document actions"
                          >
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          {canWrite ? (
                            <DropdownMenuItem onClick={() => setEditing(doc)}>
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit metadata
                            </DropdownMenuItem>
                          ) : null}
                          {canDelete ? (
                            <DropdownMenuItem
                              variant="destructive"
                              onClick={() => setDeleting(doc)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          ) : null}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}

          {documents.data && documents.data.items.length === 0 ? (
            <div className="p-4">
              <EmptyState
                icon={FileText}
                title={
                  debouncedSearch || status !== "all"
                    ? "No matching documents"
                    : "No documents yet"
                }
                description={
                  debouncedSearch || status !== "all"
                    ? "Try adjusting your search or filters."
                    : "Upload a PDF, TXT, or DOCX file to get started."
                }
                action={
                  canWrite && !debouncedSearch && status === "all" ? (
                    <Button onClick={() => setUploadOpen(true)}>
                      <Upload className="h-4 w-4" />
                      Upload document
                    </Button>
                  ) : null
                }
              />
            </div>
          ) : null}
        </CardContent>
      </Card>

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

      <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />
      {editing ? (
        <EditDocumentDialog
          key={editing.id}
          document={editing}
          onClose={() => setEditing(null)}
        />
      ) : null}

      <Dialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Delete document</DialogTitle>
            <DialogDescription>
              “{deleting?.filename}” will be permanently removed along with its
              indexed passages. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleting(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={() => deleting && deleteMutation.mutate(deleting.id)}
            >
              {deleteMutation.isPending ? <Spinner /> : null}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function UploadDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [file, setFile] = React.useState<File | null>(null);
  const [category, setCategory] = React.useState("");
  const [collection, setCollection] = React.useState("default");

  const reset = React.useCallback(() => {
    setFile(null);
    setCategory("");
    setCollection("default");
  }, []);

  const mutation = useMutation({
    mutationFn: uploadDocument,
    onSuccess: (doc) => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      reset();
      onOpenChange(false);
      if (doc.status === "failed") {
        toast.error(`${doc.filename} could not be processed`, {
          description: doc.error_message ?? undefined,
        });
      } else {
        toast.success(`${doc.filename} uploaded`);
      }
    },
    onError: (error) => toast.error(getApiError(error).message),
  });

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!file) {
      toast.error("Choose a file to upload.");
      return;
    }
    mutation.mutate({
      file,
      category: category.trim() || undefined,
      collection: collection.trim() || "default",
    });
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (mutation.isPending) return;
        if (!next) reset();
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Upload document</DialogTitle>
            <DialogDescription>
              Accepted formats: PDF, TXT, DOCX.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="file">File</Label>
            <Input
              id="file"
              type="file"
              accept={ACCEPTED}
              onChange={(event) =>
                setFile(event.target.files?.[0] ?? null)
              }
            />
            {file ? (
              <p className="text-xs text-muted-foreground">
                {file.name} · {formatBytes(file.size)}
              </p>
            ) : null}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="category">Category</Label>
              <Input
                id="category"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                placeholder="e.g. policies"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="collection">Collection</Label>
              <Input
                id="collection"
                value={collection}
                onChange={(event) => setCollection(event.target.value)}
                placeholder="default"
              />
            </div>
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
            <Button type="submit" disabled={mutation.isPending || !file}>
              {mutation.isPending ? <Spinner /> : <FileUp className="h-4 w-4" />}
              Upload
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditDocumentDialog({
  document,
  onClose,
}: {
  document: Document;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [category, setCategory] = React.useState(document.category ?? "");
  const [collection, setCollection] = React.useState(document.collection);

  const mutation = useMutation({
    mutationFn: (payload: { category: string | null; collection: string | null }) =>
      updateDocument(document.id, payload),
    onSuccess: () => {
      toast.success("Document updated");
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      onClose();
    },
    onError: (error) => toast.error(getApiError(error).message),
  });

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    mutation.mutate({
      category: category.trim() || null,
      collection: collection.trim() || null,
    });
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Edit metadata</DialogTitle>
            <DialogDescription className="truncate">
              {document.filename}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="edit-category">Category</Label>
              <Input
                id="edit-category"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-collection">Collection</Label>
              <Input
                id="edit-collection"
                value={collection}
                onChange={(event) => setCollection(event.target.value)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? <Spinner /> : null}
              Save changes
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
