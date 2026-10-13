import {
  ClipboardList,
  FileText,
  LayoutDashboard,
  MessageSquare,
  type LucideIcon,
} from "lucide-react";

import type { Permission } from "@/lib/permissions";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  permission?: Permission;
  end?: boolean;
  description: string;
}

export const NAV_ITEMS: NavItem[] = [
  {
    to: "/",
    label: "Dashboard",
    icon: LayoutDashboard,
    end: true,
    description: "Overview of your workspace",
  },
  {
    to: "/ask",
    label: "Ask",
    icon: MessageSquare,
    permission: "query:execute",
    description: "Ask questions grounded in your documents",
  },
  {
    to: "/documents",
    label: "Documents",
    icon: FileText,
    permission: "documents:read",
    description: "Upload and manage knowledge sources",
  },
  {
    to: "/evaluations",
    label: "Evaluations",
    icon: ClipboardList,
    permission: "evaluations:run",
    description: "Measure retrieval quality",
  },
];
