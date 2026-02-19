import { describe, it, expect, beforeEach } from "vitest";
import { buildApp } from "../src/app.js";
import { InMemoryRepository } from "../src/repository/index.js";
import { InMemoryConversationRepository } from "../src/repository/index.js";
import { NoopEmbeddingService } from "../src/embedding/index.js";
import { MemoryService } from "../src/services/memory-service.js";
import { ConversationService } from "../src/services/conversation-service.js";

let service: MemoryService;
let conversationService: ConversationService;

function createApp() {
  return buildApp({ service, conversationService });
}

beforeEach(() => {
  const repo = new InMemoryRepository();
  const embedding = new NoopEmbeddingService();
  service = new MemoryService(repo, embedding);

  const convRepo = new InMemoryConversationRepository();
  conversationService = new ConversationService(convRepo, embedding);
});

describe("POST /api/conversations (upsert)", () => {
  it("creates a conversation and returns 200", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: {
        sourceId: "src-1",
        title: "Test conversation",
        source: "test",
        tags: ["test"],
        messages: [
          { role: "user", content: "Hello, how are you?" },
          { role: "assistant", content: "I'm doing well!" },
        ],
      },
    });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.id).toBeDefined();
    expect(body.title).toBe("Test conversation");
    expect(body.source).toBe("test");
    expect(body.sourceId).toBe("src-1");
    expect(body.tags).toEqual(["test"]);
    expect(body.messages).toHaveLength(2);
    expect(body.messages[0].role).toBe("user");
    expect(body.messages[0].content).toBe("Hello, how are you?");
    expect(body.messages[1].role).toBe("assistant");
  });

  it("appends messages on second call with same sourceId", async () => {
    const app = createApp();
    await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: {
        sourceId: "src-append",
        title: "Append test",
        messages: [
          { role: "user", content: "First message" },
          { role: "assistant", content: "First response" },
        ],
      },
    });

    const res = await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: {
        sourceId: "src-append",
        messages: [
          { role: "user", content: "Second message" },
          { role: "assistant", content: "Second response" },
        ],
      },
    });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.messages).toHaveLength(4);
    expect(body.messages[0].position).toBe(0);
    expect(body.messages[1].position).toBe(1);
    expect(body.messages[2].position).toBe(2);
    expect(body.messages[2].content).toBe("Second message");
    expect(body.messages[3].position).toBe(3);
  });

  it("updates metadata on upsert", async () => {
    const app = createApp();
    await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: {
        sourceId: "src-meta",
        title: "Original title",
        tags: ["original"],
      },
    });

    const res = await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: {
        sourceId: "src-meta",
        title: "Updated title",
        tags: ["updated"],
      },
    });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.title).toBe("Updated title");
    expect(body.tags).toEqual(["updated"]);
  });

  it("works with only sourceId (minimal upsert)", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: {
        sourceId: "src-minimal",
      },
    });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.id).toBeDefined();
    expect(body.sourceId).toBe("src-minimal");
    expect(body.title).toBe("");
    expect(body.tags).toEqual([]);
  });

  it("returns 400 when sourceId is missing", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: {
        title: "No source id",
        messages: [{ role: "user", content: "Hello" }],
      },
    });
    expect(res.statusCode).toBe(400);
    expect(res.json().error).toBe(
      "sourceId is required and must be a non-empty string",
    );
  });

  it("returns 400 when sourceId is empty string", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: {
        sourceId: "   ",
      },
    });
    expect(res.statusCode).toBe(400);
  });

  it("returns 400 when messages is empty array", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: { sourceId: "src-empty-msgs", messages: [] },
    });
    expect(res.statusCode).toBe(400);
    expect(res.json().error).toBe(
      "messages must be a non-empty array when provided",
    );
  });

  it("returns 400 when message has no role", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: {
        sourceId: "src-bad-msg",
        messages: [{ content: "Hello" }],
      },
    });
    expect(res.statusCode).toBe(400);
    expect(res.json().error).toBe(
      "each message must have a non-empty role and content string",
    );
  });

  it("returns 400 when message has no content", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: {
        sourceId: "src-bad-msg-2",
        messages: [{ role: "user" }],
      },
    });
    expect(res.statusCode).toBe(400);
  });

  it("defaults source to empty and tags to empty array on create", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: {
        sourceId: "src-defaults",
        messages: [{ role: "user", content: "Hi" }],
      },
    });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.source).toBe("");
    expect(body.tags).toEqual([]);
  });
});

describe("GET /api/conversations", () => {
  it("returns empty list initially", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "GET",
      url: "/api/conversations",
    });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ conversations: [], total: 0 });
  });

  it("returns stored conversations via text search", async () => {
    const app = createApp();
    await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: {
        sourceId: "src-ts",
        title: "TypeScript discussion",
        messages: [
          { role: "user", content: "Tell me about TypeScript generics" },
          { role: "assistant", content: "Generics allow..." },
        ],
      },
    });

    const res = await app.inject({
      method: "GET",
      url: "/api/conversations?query=TypeScript",
    });
    const body = res.json();
    expect(body.total).toBe(1);
    expect(body.conversations[0].title).toBe("TypeScript discussion");
    expect(body.conversations[0].messages).toBeDefined();
  });

  it("filters by tags", async () => {
    const app = createApp();
    await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: {
        sourceId: "src-work",
        title: "Work chat",
        tags: ["work"],
        messages: [{ role: "user", content: "Project update" }],
      },
    });
    await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: {
        sourceId: "src-personal",
        title: "Personal chat",
        tags: ["personal"],
        messages: [{ role: "user", content: "Weekend plans" }],
      },
    });

    const res = await app.inject({
      method: "GET",
      url: "/api/conversations?tags=work",
    });
    const body = res.json();
    expect(body.total).toBe(1);
    expect(body.conversations[0].title).toBe("Work chat");
  });

  it("respects limit parameter", async () => {
    const app = createApp();
    for (let i = 0; i < 5; i++) {
      await app.inject({
        method: "POST",
        url: "/api/conversations",
        payload: {
          sourceId: `src-limit-${i}`,
          title: `Conv ${i}`,
          messages: [{ role: "user", content: `Message ${i}` }],
        },
      });
    }

    const res = await app.inject({
      method: "GET",
      url: "/api/conversations?limit=2",
    });
    const body = res.json();
    expect(body.total).toBe(2);
    expect(body.conversations).toHaveLength(2);
  });
});

describe("GET /api/conversations/:id", () => {
  it("returns a conversation by ID with messages", async () => {
    const app = createApp();
    const storeRes = await app.inject({
      method: "POST",
      url: "/api/conversations",
      payload: {
        sourceId: "src-findable",
        title: "Findable",
        messages: [
          { role: "user", content: "Question" },
          { role: "assistant", content: "Answer" },
        ],
      },
    });
    const { id } = storeRes.json();

    const res = await app.inject({
      method: "GET",
      url: `/api/conversations/${id}`,
    });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.id).toBe(id);
    expect(body.title).toBe("Findable");
    expect(body.messages).toHaveLength(2);
    expect(body.messages[0].position).toBe(0);
    expect(body.messages[1].position).toBe(1);
  });

  it("returns 404 for non-existent conversation", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "GET",
      url: "/api/conversations/00000000-0000-0000-0000-000000000000",
    });
    expect(res.statusCode).toBe(404);
    expect(res.json().error).toBe("conversation not found");
  });
});
