import { describe, expect, it } from "vitest";

import { hasPermission } from "@/lib/permissions";

describe("hasPermission", () => {
  it("grants admins every permission", () => {
    expect(hasPermission("admin", "users:manage")).toBe(true);
    expect(hasPermission("admin", "evaluations:run")).toBe(true);
  });

  it("scopes document managers to document operations", () => {
    expect(hasPermission("document_manager", "documents:delete")).toBe(true);
    expect(hasPermission("document_manager", "users:manage")).toBe(false);
  });

  it("scopes evaluators to evaluation runs", () => {
    expect(hasPermission("evaluator", "evaluations:run")).toBe(true);
    expect(hasPermission("evaluator", "documents:write")).toBe(false);
  });

  it("denies when the role is missing", () => {
    expect(hasPermission(null, "documents:read")).toBe(false);
    expect(hasPermission(undefined, "query:execute")).toBe(false);
  });
});
