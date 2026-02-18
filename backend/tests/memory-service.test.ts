import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryService } from "../src/services/memory-service.js";
import type { MemoryRepository } from "../src/repository/types.js";
import type { EmbeddingService } from "../src/embedding/types.js";
import type { Memory } from "../src/types/memory.js";

const mockMemory: Memory = {
  id: "test-id",
  content: "test content",
  tags: ["test"],
  createdAt: "2024-01-01T00:00:00.000Z",
  updatedAt: "2024-01-01T00:00:00.000Z",
};

function createMockRepo(): MemoryRepository {
  return {
    initialize: vi.fn(),
    store: vi.fn().mockResolvedValue(mockMemory),
    fetch: vi.fn().mockResolvedValue([mockMemory]),
    healthCheck: vi.fn().mockResolvedValue(true),
    close: vi.fn(),
  };
}

function createMockEmbedding(vector: number[] | null = null): EmbeddingService {
  return {
    embed: vi.fn().mockResolvedValue(vector),
    healthCheck: vi.fn().mockResolvedValue(vector !== null),
  };
}

describe("MemoryService", () => {
  let repo: MemoryRepository;
  let embedding: EmbeddingService;
  let service: MemoryService;

  const fakeVector = Array(4096).fill(0.1);

  beforeEach(() => {
    repo = createMockRepo();
    embedding = createMockEmbedding(fakeVector);
    service = new MemoryService(repo, embedding);
  });

  describe("store", () => {
    it("embeds content and passes embedding to repository", async () => {
      await service.store("hello world", ["greeting"]);

      expect(embedding.embed).toHaveBeenCalledWith("hello world");
      expect(repo.store).toHaveBeenCalledWith({
        content: "hello world",
        tags: ["greeting"],
        embedding: fakeVector,
      });
    });

    it("stores with null embedding when embedding service fails", async () => {
      embedding = createMockEmbedding(null);
      service = new MemoryService(repo, embedding);

      await service.store("hello world", ["greeting"]);

      expect(repo.store).toHaveBeenCalledWith({
        content: "hello world",
        tags: ["greeting"],
        embedding: null,
      });
    });
  });

  describe("fetch", () => {
    it("embeds query and uses vector search when embedding succeeds", async () => {
      await service.fetch("search query", ["tag"]);

      expect(embedding.embed).toHaveBeenCalledWith("search query");
      expect(repo.fetch).toHaveBeenCalledWith({
        query: "search query",
        tags: ["tag"],
        queryEmbedding: fakeVector,
      });
    });

    it("falls back to text search when embedding returns null", async () => {
      embedding = createMockEmbedding(null);
      service = new MemoryService(repo, embedding);

      await service.fetch("search query", ["tag"]);

      expect(embedding.embed).toHaveBeenCalledWith("search query");
      expect(repo.fetch).toHaveBeenCalledWith({
        query: "search query",
        tags: ["tag"],
      });
    });

    it("uses text search when no query is provided", async () => {
      await service.fetch(undefined, ["tag"]);

      expect(embedding.embed).not.toHaveBeenCalled();
      expect(repo.fetch).toHaveBeenCalledWith({
        query: undefined,
        tags: ["tag"],
      });
    });

    it("fetches all memories when no query or tags", async () => {
      await service.fetch();

      expect(embedding.embed).not.toHaveBeenCalled();
      expect(repo.fetch).toHaveBeenCalledWith({
        query: undefined,
        tags: undefined,
      });
    });
  });

  describe("lifecycle", () => {
    it("delegates initialize to repository", async () => {
      await service.initialize();
      expect(repo.initialize).toHaveBeenCalled();
    });

    it("delegates healthCheck to repository", async () => {
      const result = await service.healthCheck();
      expect(repo.healthCheck).toHaveBeenCalled();
      expect(result).toBe(true);
    });

    it("delegates close to repository", async () => {
      await service.close();
      expect(repo.close).toHaveBeenCalled();
    });
  });
});
