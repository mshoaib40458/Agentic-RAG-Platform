export const queryKeys = {
  health: ["health"] as const,
  documentStats: ["documents", "stats"] as const,
  documents: (params: object) =>
    ["documents", "list", params] as const,
  document: (id: string) => ["documents", "detail", id] as const,
  queries: (params: object) =>
    ["queries", "list", params] as const,
  query: (id: string) => ["queries", "detail", id] as const,
  conversations: (params: object) =>
    ["conversations", "list", params] as const,
  conversation: (id: string) => ["conversations", "detail", id] as const,
  evaluations: (params: object) =>
    ["evaluations", "list", params] as const,
  evaluation: (id: string) => ["evaluations", "detail", id] as const,
  users: (params: object) =>
    ["users", "list", params] as const,
};
