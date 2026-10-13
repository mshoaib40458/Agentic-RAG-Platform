import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "@/components/error-boundary";

function Boom(): ReactElement {
  throw new Error("boom");
}

describe("ErrorBoundary", () => {
  it("renders the default fallback and reports the error", () => {
    const onError = vi.fn();
    const consoleSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);

    render(
      <ErrorBoundary onError={onError}>
        <Boom />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("boom");
    expect(onError).toHaveBeenCalledTimes(1);
    consoleSpy.mockRestore();
  });

  it("supports a custom fallback", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary fallback={(error) => <p>custom {error.message}</p>}>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText("custom boom")).toBeInTheDocument();
    spy.mockRestore();
  });
});
