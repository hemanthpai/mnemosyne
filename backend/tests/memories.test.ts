import { describe, it, expect, beforeEach, vi } from "vitest";
import { buildApp } from "../src/app.js";
import { InMemoryRepository } from "../src/repository/index.js";
import { NoopEmbeddingService } from "../src/embedding/index.js";
import { MemoryService } from "../src/services/memory-service.js";

let service: MemoryService;

function createApp(svc?: MemoryService) {
  return buildApp({ service: svc ?? service });
}

beforeEach(() => {
  const repo = new InMemoryRepository();
  const embedding = new NoopEmbeddingService();
  service = new MemoryService(repo, embedding);
});

describe("GET /health", () => {
  it("returns ok", async () => {
    const app = createApp();
    const res = await app.inject({ method: "GET", url: "/health" });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ status: "ok" });
  });

  it("returns 503 when repository is unhealthy", async () => {
    const unhealthyService: MemoryService = {
      initialize: vi.fn(),
      store: vi.fn(),
      fetch: vi.fn(),
      healthCheck: vi.fn().mockResolvedValue(false),
      close: vi.fn(),
    } as unknown as MemoryService;
    const app = createApp(unhealthyService);
    const res = await app.inject({ method: "GET", url: "/health" });
    expect(res.statusCode).toBe(503);
    expect(res.json()).toEqual({ status: "unhealthy" });
  });
});

describe("POST /api/memories", () => {
  it("stores a memory and returns 201", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "POST",
      url: "/api/memories",
      payload: { content: "Test memory", tags: ["test"] },
    });
    expect(res.statusCode).toBe(201);
    const body = res.json();
    expect(body.id).toBeDefined();
    expect(body.content).toBe("Test memory");
    expect(body.tags).toEqual(["test"]);
    expect(body.createdAt).toBeDefined();
    expect(body.updatedAt).toBeDefined();
  });

  it("returns 400 when content is missing", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "POST",
      url: "/api/memories",
      payload: { tags: ["test"] },
    });
    expect(res.statusCode).toBe(400);
    expect(res.json().error).toBe(
      "content is required and must be a non-empty string",
    );
  });

  it("returns 400 when content is empty string", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "POST",
      url: "/api/memories",
      payload: { content: "   " },
    });
    expect(res.statusCode).toBe(400);
  });

  it("defaults tags to empty array when not provided", async () => {
    const app = createApp();
    const res = await app.inject({
      method: "POST",
      url: "/api/memories",
      payload: { content: "No tags memory" },
    });
    expect(res.statusCode).toBe(201);
    expect(res.json().tags).toEqual([]);
  });
});

describe("GET /api/memories", () => {
  it("returns empty list initially", async () => {
    const app = createApp();
    const res = await app.inject({ method: "GET", url: "/api/memories" });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ memories: [], total: 0 });
  });

  it("returns stored memories", async () => {
    const app = createApp();
    await app.inject({
      method: "POST",
      url: "/api/memories",
      payload: { content: "Memory 1", tags: ["a"] },
    });
    await app.inject({
      method: "POST",
      url: "/api/memories",
      payload: { content: "Memory 2", tags: ["b"] },
    });

    const res = await app.inject({ method: "GET", url: "/api/memories" });
    const body = res.json();
    expect(body.total).toBe(2);
    expect(body.memories).toHaveLength(2);
  });

  it("filters by query text", async () => {
    const app = createApp();
    await app.inject({
      method: "POST",
      url: "/api/memories",
      payload: { content: "I love TypeScript" },
    });
    await app.inject({
      method: "POST",
      url: "/api/memories",
      payload: { content: "Python is great" },
    });

    const res = await app.inject({
      method: "GET",
      url: "/api/memories?query=typescript",
    });
    const body = res.json();
    expect(body.total).toBe(1);
    expect(body.memories[0].content).toBe("I love TypeScript");
  });

  it("filters by tags", async () => {
    const app = createApp();
    await app.inject({
      method: "POST",
      url: "/api/memories",
      payload: { content: "Memory A", tags: ["work", "project"] },
    });
    await app.inject({
      method: "POST",
      url: "/api/memories",
      payload: { content: "Memory B", tags: ["personal"] },
    });

    const res = await app.inject({
      method: "GET",
      url: "/api/memories?tags=work",
    });
    const body = res.json();
    expect(body.total).toBe(1);
    expect(body.memories[0].content).toBe("Memory A");
  });

  it("filters by both query and tags", async () => {
    const app = createApp();
    await app.inject({
      method: "POST",
      url: "/api/memories",
      payload: { content: "Work meeting notes", tags: ["work"] },
    });
    await app.inject({
      method: "POST",
      url: "/api/memories",
      payload: { content: "Work lunch spot", tags: ["personal"] },
    });
    await app.inject({
      method: "POST",
      url: "/api/memories",
      payload: { content: "Grocery list", tags: ["personal"] },
    });

    const res = await app.inject({
      method: "GET",
      url: "/api/memories?query=work&tags=work",
    });
    const body = res.json();
    expect(body.total).toBe(1);
    expect(body.memories[0].content).toBe("Work meeting notes");
  });
});
