import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  ChevronDown,
  MessageSquare,
  MoreVertical,
  Plus,
  Send,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import {
  deleteConversation,
  getConversation,
  listConversations,
} from "@/api/conversations";
import { submitFeedback } from "@/api/feedback";
import { submitQuery } from "@/api/query";
import { PageHeader } from "@/components/page-header";
import { Spinner } from "@/components/spinner";
import { VerificationBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { getApiError } from "@/lib/api-client";
import { formatDuration, formatRelative } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import type { Citation, Conversation, Query } from "@/types/api";

const SUGGESTIONS = [
  "Summarise the key points across my documents.",
  "What are the main policies and their requirements?",
  "Which documents mention compliance or deadlines?",
];

export function AskPage() {
  const queryClient = useQueryClient();

  const [conversationId, setConversationId] = React.useState<string | null>(null);
  const [messages, setMessages] = React.useState<Query[]>([]);
  const [loadingHistory, setLoadingHistory] = React.useState(false);
  const [pendingQuestion, setPendingQuestion] = React.useState<string | null>(
    null,
  );
  const [question, setQuestion] = React.useState("");
  const [showFilters, setShowFilters] = React.useState(false);
  const [category, setCategory] = React.useState("");
  const [collection, setCollection] = React.useState("");
  const [topK, setTopK] = React.useState("");
  const [feedback, setFeedback] = React.useState<Record<string, number>>({});
  const bottomRef = React.useRef<HTMLDivElement>(null);

  const conversationsQuery = useQuery({
    queryKey: queryKeys.conversations({ limit: 50 }),
    queryFn: () => listConversations({ limit: 50 }),
  });

  const openConversation = React.useCallback(async (id: string) => {
    setConversationId(id);
    setPendingQuestion(null);
    setMessages([]);
    setLoadingHistory(true);
    try {
      const detail = await getConversation(id);
      setMessages(detail.turns);
    } catch (error) {
      toast.error(getApiError(error).message);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  const mutation = useMutation({
    mutationFn: submitQuery,
    onSuccess: (result) => {
      setPendingQuestion(null);
      setMessages((prev) => [...prev, result]);
      if (result.conversation_id) setConversationId(result.conversation_id);
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
    onError: (error) => {
      setPendingQuestion(null);
      toast.error(getApiError(error).message);
    },
  });

  const removeMutation = useMutation({
    mutationFn: deleteConversation,
    onSuccess: (_data, id) => {
      toast.success("Conversation deleted");
      if (id === conversationId) {
        setConversationId(null);
        setMessages([]);
        setPendingQuestion(null);
      }
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
    onError: (error) => toast.error(getApiError(error).message),
  });

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pendingQuestion]);

  const startNewChat = React.useCallback(() => {
    setConversationId(null);
    setMessages([]);
    setPendingQuestion(null);
    setQuestion("");
  }, []);

  const ask = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed || mutation.isPending) return;
    setPendingQuestion(trimmed);
    setQuestion("");
    mutation.mutate({
      question: trimmed,
      conversation_id: conversationId ?? undefined,
      top_k: topK ? Number(topK) : undefined,
      filters: {
        category: category.trim() || undefined,
        collection: collection.trim() || undefined,
      },
    });
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    ask(question);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      ask(question);
    }
  };

  const sendFeedback = async (queryId: string, rating: number) => {
    try {
      await submitFeedback({ query_id: queryId, rating });
      setFeedback((prev) => ({ ...prev, [queryId]: rating }));
      toast.success("Thanks for the feedback");
    } catch (error) {
      toast.error(getApiError(error).message);
    }
  };

  const conversations = conversationsQuery.data?.items ?? [];
  const activeConversation = conversations.find(
    (item) => item.id === conversationId,
  );
  const panelTitle =
    activeConversation?.title ??
    (messages.length > 0 ? messages[0].question : "New chat");
  const isEmpty = messages.length === 0 && !pendingQuestion && !loadingHistory;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Ask"
        description="Chat with your documents. Follow-up questions keep the full conversation context."
      />

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <ConversationSidebar
          conversations={conversations}
          activeId={conversationId}
          loading={conversationsQuery.isLoading}
          deleting={removeMutation.isPending}
          onSelect={(id) => void openConversation(id)}
          onDelete={(id) => removeMutation.mutate(id)}
          onNew={startNewChat}
        />

        <Card className="flex flex-col overflow-hidden">
          <CardHeader className="border-b py-4">
            <div className="flex items-center gap-3">
              <div className="min-w-0 flex-1">
                <CardTitle className="truncate text-base">{panelTitle}</CardTitle>
                <CardDescription>
                  {messages.length > 0
                    ? `${messages.length} ${
                        messages.length === 1 ? "message" : "messages"
                      }`
                    : "Ask a question to start the conversation."}
                </CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={startNewChat}>
                <Plus className="h-4 w-4" />
                New
              </Button>
            </div>
          </CardHeader>

          <CardContent className="p-0">
            <ScrollArea className="h-[60vh]">
              <div className="space-y-6 p-4 sm:p-5">
                {isEmpty ? (
                  <EmptyState suggestions={SUGGESTIONS} onPick={ask} />
                ) : null}

                {messages.map((item) => (
                  <React.Fragment key={item.id}>
                    <UserBubble text={item.question} />
                    <AssistantMessage
                      query={item}
                      rating={feedback[item.id] ?? null}
                      onFeedback={(rating) => void sendFeedback(item.id, rating)}
                    />
                  </React.Fragment>
                ))}

                {loadingHistory ? <AnswerSkeleton /> : null}

                {pendingQuestion ? (
                  <>
                    <UserBubble text={pendingQuestion} />
                    <AnswerSkeleton />
                  </>
                ) : null}

                <div ref={bottomRef} />
              </div>
            </ScrollArea>
          </CardContent>

          <div className="border-t p-4">
            <form onSubmit={handleSubmit} className="space-y-3">
              <Textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a follow-up question…"
                className="min-h-[56px] resize-none"
                maxLength={2000}
              />
              <div className="flex flex-wrap items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => setShowFilters((value) => !value)}
                  className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  <ChevronDown
                    className={cn(
                      "h-4 w-4 transition-transform",
                      showFilters && "rotate-180",
                    )}
                  />
                  Filters
                </button>
                <div className="flex items-center gap-3">
                  <span className="hidden text-xs text-muted-foreground sm:inline">
                    ⌘/Ctrl + Enter
                  </span>
                  <Button
                    type="submit"
                    disabled={mutation.isPending || !question.trim()}
                  >
                    {mutation.isPending ? (
                      <Spinner />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                    Send
                  </Button>
                </div>
              </div>

              {showFilters ? (
                <div className="grid gap-4 rounded-lg border bg-muted/30 p-4 sm:grid-cols-3">
                  <div className="space-y-2">
                    <Label htmlFor="filter-category">Category</Label>
                    <Input
                      id="filter-category"
                      value={category}
                      onChange={(event) => setCategory(event.target.value)}
                      placeholder="Any"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="filter-collection">Collection</Label>
                    <Input
                      id="filter-collection"
                      value={collection}
                      onChange={(event) => setCollection(event.target.value)}
                      placeholder="Any"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="filter-topk">Passages (top-k)</Label>
                    <Input
                      id="filter-topk"
                      type="number"
                      min={1}
                      max={50}
                      value={topK}
                      onChange={(event) => setTopK(event.target.value)}
                      placeholder="Default"
                    />
                  </div>
                </div>
              ) : null}
            </form>
          </div>
        </Card>
      </div>
    </div>
  );
}

function ConversationSidebar({
  conversations,
  activeId,
  loading,
  deleting,
  onSelect,
  onDelete,
  onNew,
}: {
  conversations: Conversation[];
  activeId: string | null;
  loading: boolean;
  deleting: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onNew: () => void;
}) {
  return (
    <Card className="flex flex-col overflow-hidden">
      <CardHeader className="flex-row items-center justify-between space-y-0 border-b py-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <MessageSquare className="h-4 w-4 text-muted-foreground" />
          Chats
        </CardTitle>
        <Button variant="ghost" size="sm" onClick={onNew}>
          <Plus className="h-4 w-4" />
          New
        </Button>
      </CardHeader>
      <CardContent className="p-2">
        <ScrollArea className="h-[60vh]">
          {loading ? (
            <div className="space-y-2 p-1">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : conversations.length === 0 ? (
            <p className="px-3 py-8 text-center text-sm text-muted-foreground">
              No conversations yet. Ask a question to start one.
            </p>
          ) : (
            <div className="space-y-1">
              {conversations.map((conversation) => (
                <ConversationRow
                  key={conversation.id}
                  conversation={conversation}
                  active={conversation.id === activeId}
                  deleting={deleting}
                  onSelect={onSelect}
                  onDelete={onDelete}
                />
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

function ConversationRow({
  conversation,
  active,
  deleting,
  onSelect,
  onDelete,
}: {
  conversation: Conversation;
  active: boolean;
  deleting: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div
      className={cn(
        "group flex items-center gap-1 rounded-lg transition-colors",
        active ? "bg-accent" : "hover:bg-accent/50",
      )}
    >
      <button
        type="button"
        onClick={() => onSelect(conversation.id)}
        className="min-w-0 flex-1 px-3 py-2 text-left"
      >
        <span className="block truncate text-sm font-medium">
          {conversation.title}
        </span>
        <span className="block text-xs text-muted-foreground">
          {conversation.turn_count}{" "}
          {conversation.turn_count === 1 ? "message" : "messages"} ·{" "}
          {formatRelative(conversation.updated_at)}
        </span>
      </button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Conversation options"
            className="mr-1 h-8 w-8 shrink-0 text-muted-foreground"
            disabled={deleting}
          >
            <MoreVertical className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            variant="destructive"
            disabled={deleting}
            onSelect={() => onDelete(conversation.id)}
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

function EmptyState({
  suggestions,
  onPick,
}: {
  suggestions: string[];
  onPick: (value: string) => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-5 py-12 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Sparkles className="h-5 w-5" />
      </div>
      <div className="space-y-1">
        <p className="font-medium">Ask your documents anything</p>
        <p className="text-sm text-muted-foreground">
          Answers are grounded in your indexed documents, with citations. Ask
          follow-ups and the context carries over.
        </p>
      </div>
      <div className="flex w-full max-w-md flex-col gap-2">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onPick(suggestion)}
            className="flex items-center gap-3 rounded-lg border bg-background px-3 py-2.5 text-left text-sm transition-colors hover:bg-accent"
          >
            <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground">
        {text}
      </div>
    </div>
  );
}

function AnswerSkeleton() {
  return (
    <div className="flex justify-start">
      <div className="flex max-w-[85%] items-center gap-3 rounded-2xl rounded-bl-sm border bg-muted/40 px-4 py-3">
        <Spinner className="text-primary" />
        <span className="text-sm text-muted-foreground">
          Retrieving passages and verifying the answer…
        </span>
      </div>
    </div>
  );
}

function AssistantMessage({
  query,
  rating,
  onFeedback,
}: {
  query: Query;
  rating: number | null;
  onFeedback: (rating: number) => void;
}) {
  const answer = query.answer;

  if (query.status === "failed" || !answer) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {query.error_message ??
            "The request failed. Please try again in a moment."}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[85%] space-y-2">
        <div className="rounded-2xl rounded-bl-sm border bg-muted/40 px-4 py-3">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <VerificationBadge status={answer.verification_status} />
            {query.intent ? <span>intent: {query.intent}</span> : null}
            <span className="ml-auto">
              {formatDuration(query.latency_ms)}
              {answer.model ? ` · ${answer.model}` : ""}
            </span>
          </div>
          <div className="whitespace-pre-wrap text-sm leading-relaxed">
            {answer.content}
          </div>
        </div>

        {answer.citations.length > 0 ? (
          <details className="rounded-lg border bg-background/50 px-3 py-2">
            <summary className="flex cursor-pointer items-center gap-2 text-xs font-medium text-muted-foreground">
              <BookOpen className="h-3.5 w-3.5" />
              Sources ({answer.citations.length})
            </summary>
            <div className="mt-2 space-y-2">
              {answer.citations.map((citation, index) => (
                <CitationCard
                  key={citation.chunk_id}
                  citation={citation}
                  index={index + 1}
                />
              ))}
            </div>
          </details>
        ) : null}

        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <span className="mr-1">Helpful?</span>
          <Button
            variant={rating === 1 ? "default" : "ghost"}
            size="icon"
            aria-label="Helpful"
            onClick={() => onFeedback(1)}
          >
            <ThumbsUp className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant={rating === -1 ? "destructive" : "ghost"}
            size="icon"
            aria-label="Not helpful"
            onClick={() => onFeedback(-1)}
          >
            <ThumbsDown className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function CitationCard({
  citation,
  index,
}: {
  citation: Citation;
  index: number;
}) {
  return (
    <div className="rounded-lg border bg-muted/30 p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-primary/10 text-xs font-medium text-primary">
            {index}
          </span>
          <span className="truncate text-sm font-medium">
            {citation.document_name}
          </span>
          {citation.page !== null ? (
            <span className="shrink-0 text-xs text-muted-foreground">
              p. {citation.page}
            </span>
          ) : null}
        </div>
        <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
          {citation.score.toFixed(3)}
        </span>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{citation.snippet}</p>
    </div>
  );
}
