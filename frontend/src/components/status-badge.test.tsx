import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  DocumentStatusBadge,
  QueryStatusBadge,
  VerificationBadge,
} from "@/components/status-badge";

describe("status badges", () => {
  it("renders a humanised document status", () => {
    render(<DocumentStatusBadge status="indexed" />);
    expect(screen.getByText("Indexed")).toBeInTheDocument();
  });

  it("renders a humanised query status", () => {
    render(<QueryStatusBadge status="completed" />);
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("uses friendly verification labels", () => {
    render(<VerificationBadge status="partially_supported" />);
    expect(screen.getByText("Partially verified")).toBeInTheDocument();
  });
});
