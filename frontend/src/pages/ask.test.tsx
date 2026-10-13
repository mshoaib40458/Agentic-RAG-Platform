import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/conversations", () => ({
  listConversations: vi.fn().mockResolvedValue({
    items: [
      {
        id: "c1",
        title: "Test chat",
        turn_count: 1,
        updated_at: new Date().toISOString(),
      },
    ],
    total: 1,
  }),
  getConversation: vi.fn(),
  deleteConversation: vi.fn(),
}));
vi.mock("@/api/query", () => ({ submitQuery: vi.fn() }));
vi.mock("@/api/feedback", () => ({ submitFeedback: vi.fn() }));

import { AskPage } from "@/pages/ask";

describe("AskPage conversation actions", () => {
  it("renders a three-dot options menu for each conversation", async () => {
    Element.prototype.scrollIntoView = vi.fn();
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <AskPage />
      </QueryClientProvider>,
    );
    expect(
      await screen.findByLabelText("Conversation options"),
    ).toBeInTheDocument();
  });
});
