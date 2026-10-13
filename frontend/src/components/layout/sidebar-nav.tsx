import { NavLink } from "react-router-dom";
import { Sparkles } from "lucide-react";

import { NAV_ITEMS } from "@/components/layout/nav-config";
import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";

export function Brand({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
        <Sparkles className="h-5 w-5" />
      </span>
      <span className="flex flex-col leading-none">
        <span className="text-sm font-semibold">Agentic RAG</span>
        <span className="text-xs text-muted-foreground">Platform</span>
      </span>
    </div>
  );
}

interface SidebarNavProps {
  onNavigate?: () => void;
  showBrand?: boolean;
}

export function SidebarNav({ onNavigate, showBrand = true }: SidebarNavProps) {
  const { can } = useAuth();
  const items = NAV_ITEMS.filter(
    (item) => !item.permission || can(item.permission),
  );

  return (
    <div className="flex h-full flex-col gap-6">
      {showBrand ? (
        <div className="px-2 pt-1">
          <Brand />
        </div>
      ) : null}
      <nav className="flex flex-1 flex-col gap-1">
        {items.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
