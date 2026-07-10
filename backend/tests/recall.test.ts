import { describe, it, expect, beforeEach, vi } from "vitest";
import { buildApp } from "../src/app.js";
import { InMemoryRepository } from "../src/repository/index.js";
import { InMemoryConversationRepository } from "../src/repository/index.js";
import { NoopEmbeddingService } from "../src/embedding/index.js";
import { MemoryService } from "../src/services/memory-service.js";
import { ConversationService } from "../src/services/conversation-service.js";
import { RecallService } from "../src/services/recall-service.js";
import type { LlmClient } from "../src/services/llm-client.js";

function createMockLlmClient(overrides?: {
  queryResponse?: string | ((userMessage: string) => string);
  extractResponse?: string;
}): LlmClient {
  const extractResponse =
    overrides?.extractResponse ?? "Relevant information extracted from conversation.";

  return {
    chatCompletion: vi.fn().mockImplementation(async (options) => {
      // Query generation uses json_schema response format
      if (options.responseFormat) {
        if (typeof overrides?.queryResponse === "function") {
          return overrides.queryResponse(options.messages[1].content);
        }
        if (typeof overrides?.queryResponse === "string") {
          return overrides.queryResponse;
        }
        // Default: echo back the user's query so text search can match
        const userQuery = options.messages[1].content;
        return JSON.stringify({ queries: [userQuery] });
      }
      // Extraction uses lower temperature
      return extractResponse;
    }),
  };
}

let service: MemoryService;
let conversationService: ConversationService;

function createApp(llmClient?: LlmClient) {
  const mockLlm = llmClient ?? createMockLlmClient();
  const recallService = new RecallService(conversationService, mockLlm);
  return buildApp({ service, conversationService, recallService });
}

async function seedConversation(
  app: ReturnType<typeof buildApp>,
  sourceId: string,
  title: string,
  messages: { role: string; content: string }[],
  userId?: string,
) {
  await app.inject({
    method: "POST",
    url: "/api/conversations",
    payload: { sourceId, title, messages, userId },
  });
}

beforeEach(() => {
  const repo = new InMemoryRepository();
  const embedding = new NoopEmbeddingService();
  service = new MemoryService(repo, embedding);

  const convRepo = new InMemoryConversationRepository();
  conversationService = new ConversationService(convRepo, embedding);
});

describe("POST /api/recall", () => {
  it("returns 400 when query is missing", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "POST",
      url: "/api/recall",
      payload: {},
    });
    expect(res.statusCode).toBe(400);
    expect(res.json().error).toBe(
      "query is required and must be a non-empty string",
    );
  });

  it("returns 400 when query is empty string", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "POST",
      url: "/api/recall",
      payload: { query: "   " },
    });
    expect(res.statusCode).toBe(400);
  });

  it("returns empty context when no conversations exist", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "POST",
      url: "/api/recall",
      payload: { query: "test query" },
    });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.context).toBe("");
    expect(body.conversations).toEqual([]);
    expect(body.totalFound).toBe(0);
  });

  it("returns formatted markdown context from matching conversations", async () => {
    const app = createApp();

    await seedConversation(app, "src-1", "TypeScript Discussion", [
      { role: "user", content: "Tell me about TypeScript generics and how they work" },
      { role: "assistant", content: "Generics allow you to create reusable components..." },
    ]);

    const res = await app.inject({
      method: "POST",
      url: "/api/recall",
      payload: { query: "TypeScript" },
    });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.context).toContain("## Relevant Context from Past Conversations");
    expect(body.context).toContain("### From: TypeScript Discussion");
    expect(body.conversations).toHaveLength(1);
    expect(body.conversations[0].title).toBe("TypeScript Discussion");
    expect(body.totalFound).toBe(1);
  });

  it("returns empty context when LLM extraction returns NONE", async () => {
    const mockLlm = createMockLlmClient({ extractResponse: "NONE" });
    const app = createApp(mockLlm);

    await seedConversation(app, "src-1", "Irrelevant Chat", [
      { role: "user", content: "Something totally unrelated to the query we will make" },
      { role: "assistant", content: "Sure!" },
    ]);

    const res = await app.inject({
      method: "POST",
      url: "/api/recall",
      payload: { query: "test" },
    });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.context).toBe("");
  });

  it("filters by userId when provided", async () => {
    const app = createApp();

    await seedConversation(
      app,
      "src-user-a",
      "User A Chat",
      [
        { role: "user", content: "This is a conversation from user A about programming" },
        { role: "assistant", content: "Great topic!" },
      ],
      "user-a",
    );

    await seedConversation(
      app,
      "src-user-b",
      "User B Chat",
      [
        { role: "user", content: "This is a conversation from user B about programming" },
        { role: "assistant", content: "Also great!" },
      ],
      "user-b",
    );

    const res = await app.inject({
      method: "POST",
      url: "/api/recall",
      payload: { query: "programming", userId: "user-a" },
    });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    // With userId scoping, should only find user-a's conversations
    for (const conv of body.conversations) {
      expect(conv.title).not.toBe("User B Chat");
    }
  });

  it("falls back to original query when LLM query generation fails", async () => {
    const mockLlm = createMockLlmClient({
      queryResponse: "not valid json",
    });
    const app = createApp(mockLlm);

    await seedConversation(app, "src-1", "Test Conv", [
      { role: "user", content: "A message about testing that should be findable" },
      { role: "assistant", content: "Found it!" },
    ]);

    const res = await app.inject({
      method: "POST",
      url: "/api/recall",
      payload: { query: "testing" },
    });
    expect(res.statusCode).toBe(200);
    // Should not error, just use the original query as fallback
  });

  it("calls LLM with correct models", async () => {
    const mockLlm = createMockLlmClient();
    const app = createApp(mockLlm);

    await seedConversation(app, "src-1", "Test Conv", [
      { role: "user", content: "A message long enough to potentially match queries" },
      { role: "assistant", content: "Response" },
    ]);

    await app.inject({
      method: "POST",
      url: "/api/recall",
      payload: { query: "test" },
    });

    const calls = (mockLlm.chatCompletion as ReturnType<typeof vi.fn>).mock
      .calls;
    // First call should be query generation
    expect(calls[0][0].model).toBe("nousresearch/hermes-4-70b");
    expect(calls[0][0].responseFormat).toBeDefined();
    // If there are extractions, second call should use extract model
    if (calls.length > 1) {
      expect(calls[1][0].model).toBe("openai/Hermes-4.3-36b");
      expect(calls[1][0].temperature).toBe(0.3);
    }
  });
});
