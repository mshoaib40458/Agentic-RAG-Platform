import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { listUsers, updateUser } from "@/api/users";
import { PageHeader } from "@/components/page-header";
import { QueryError } from "@/components/query-error";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
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
import { formatDate } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { User, UserRole } from "@/types/api";

const ROLES: UserRole[] = ["admin", "document_manager", "evaluator", "user"];

const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Admin",
  document_manager: "Document manager",
  evaluator: "Evaluator",
  user: "User",
};

export function UsersPage() {
  const { user: currentUser } = useAuth();

  const users = useQuery({
    queryKey: queryKeys.users({}),
    queryFn: () => listUsers(),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        description="Manage roles and access for everyone in the workspace."
      />

      <Card>
        <CardContent className="p-0">
          {users.isLoading ? (
            <div className="space-y-3 p-4">
              {Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-12 rounded-lg" />
              ))}
            </div>
          ) : null}

          {users.isError ? (
            <div className="p-4">
              <QueryError error={users.error} onRetry={() => users.refetch()} />
            </div>
          ) : null}

          {users.data ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead className="hidden md:table-cell">Role</TableHead>
                  <TableHead className="hidden lg:table-cell">Joined</TableHead>
                  <TableHead>Active</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.data.items.map((user) => (
                  <UserRow
                    key={user.id}
                    user={user}
                    isSelf={user.id === currentUser?.id}
                  />
                ))}
              </TableBody>
            </Table>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

function UserRow({ user, isSelf }: { user: User; isSelf: boolean }) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (payload: { role?: UserRole; is_active?: boolean }) =>
      updateUser(user.id, payload),
    onSuccess: () => {
      toast.success("User updated");
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (error) => toast.error(getApiError(error).message),
  });

  return (
    <TableRow>
      <TableCell>
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
            {user.username.slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">
              {user.username}
              {isSelf ? (
                <span className="ml-2 text-xs text-muted-foreground">you</span>
              ) : null}
            </p>
            <p className="truncate text-xs text-muted-foreground">
              {user.email}
            </p>
          </div>
        </div>
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Select
          value={user.role}
          disabled={isSelf || mutation.isPending}
          onValueChange={(next) => mutation.mutate({ role: next as UserRole })}
        >
          <SelectTrigger className="w-44" aria-label={`Role for ${user.username}`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ROLES.map((role) => (
              <SelectItem key={role} value={role}>
                {ROLE_LABELS[role]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </TableCell>
      <TableCell className="hidden text-muted-foreground lg:table-cell">
        {formatDate(user.created_at)}
      </TableCell>
      <TableCell>
        <Switch
          checked={user.is_active}
          disabled={isSelf || mutation.isPending}
          onCheckedChange={(checked) => mutation.mutate({ is_active: checked })}
          aria-label={`Toggle active for ${user.username}`}
        />
      </TableCell>
    </TableRow>
  );
}
