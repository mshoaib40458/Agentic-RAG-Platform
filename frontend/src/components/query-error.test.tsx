import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { QueryError } from "@/components/query-error";

describe("QueryError", () => {
  it("shows the API error message", () => {
    render(<QueryError error={new Error("network down")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("network down");
  });

  it("invokes the retry handler", async () => {
    const onRetry = vi.fn();
    render(<QueryError error={new Error("failed")} onRetry={onRetry} />);
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
