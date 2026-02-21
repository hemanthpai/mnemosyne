import { describe, it, expect, vi, beforeEach } from "vitest";
import { ConversationService } from "../src/services/conversation-service.js";
import type { ConversationRepository } from "../src/repository/conversation-types.js";
import type { EmbeddingService } from "../src/embedding/types.js";
import type { Conversation } from "../src/types/conversation.js";

const mockConversation: Conversation = {
  id: "conv-1",
  title: "Test conversation",
  source: "test",
  tags: ["test"],
  createdAt: "2024-01-01T00:00:00.000Z",
  updatedAt: "2024-01-01T00:00:00.000Z",
  messages: [
    {
      id: "msg-1",
      conversationId: "conv-1",
      role: "user",
      content: "This is a long enough user message for embedding to trigger properly",
      position: 0,
      createdAt: "2024-01-01T00:00:00.000Z",
    },
  ],
};

function createMockRepo(): ConversationRepository {
  return {
    initialize: vi.fn(),
    store: vi.fn().mockResolvedValue(mockConversation),
    search: vi.fn().mockResolvedValue([mockConversation]),
    getById: vi.fn().mockResolvedValue(mockConversation),
    findBySourceId: vi.fn().mockResolvedValue(null),
    upsert: vi.fn().mockResolvedValue(mockConversation),
    healthCheck: vi.fn().mockResolvedValue(true),
    close: vi.fn(),
  };
}

function createMockEmbedding(
  vector: number[] | null = null,
): EmbeddingService {
  return {
    embed: vi.fn().mockResolvedValue(vector),
    healthCheck: vi.fn().mockResolvedValue(vector !== null),
  };
}

describe("ConversationService", () => {
  let repo: ConversationRepository;
  let embedding: EmbeddingService;
  let service: ConversationService;

  const fakeVector = Array(4096).fill(0.1);

  beforeEach(() => {
    repo = createMockRepo();
    embedding = createMockEmbedding(fakeVector);
    service = new ConversationService(repo, embedding);
  });

  describe("store", () => {
    it("embeds user messages >= 50 chars", async () => {
      const longMsg = "This is a user message that is definitely longer than fifty characters in total";
      await service.store("Test", [
        { role: "user", content: longMsg },
        { role: "assistant", content: "Sure, here is a long response about that topic." },
      ]);

      expect(embedding.embed).toHaveBeenCalledTimes(1);
      expect(embedding.embed).toHaveBeenCalledWith(longMsg);

      const storeCall = (repo.store as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(storeCall.messages[0].embedding).toEqual(fakeVector);
      expect(storeCall.messages[1].embedding).toBeNull();
    });

    it("skips embedding for short user messages", async () => {
      await service.store("Test", [
        { role: "user", content: "Hi there" },
        { role: "user", content: "Yes" },
      ]);

      expect(embedding.embed).not.toHaveBeenCalled();

      const storeCall = (repo.store as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(storeCall.messages[0].embedding).toBeNull();
      expect(storeCall.messages[1].embedding).toBeNull();
    });

    it("skips embedding for assistant messages regardless of length", async () => {
      const longAssistant = "This is a very long assistant response that goes on and on about various topics";
      await service.store("Test", [
        { role: "assistant", content: longAssistant },
      ]);

      expect(embedding.embed).not.toHaveBeenCalled();
    });

    it("passes source, sourceId, and tags to repository", async () => {
      await service.store("Test", [{ role: "user", content: "Hello" }], {
        source: "webui",
        sourceId: "abc-123",
        tags: ["imported"],
      });

      const storeCall = (repo.store as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(storeCall.source).toBe("webui");
      expect(storeCall.sourceId).toBe("abc-123");
      expect(storeCall.tags).toEqual(["imported"]);
    });

    it("defaults source to empty string and tags to empty array", async () => {
      await service.store("Test", [{ role: "user", content: "Hello" }]);

      const storeCall = (repo.store as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(storeCall.source).toBe("");
      expect(storeCall.tags).toEqual([]);
    });
  });

  describe("upsert", () => {
    it("embeds new user messages >= 50 chars", async () => {
      const longMsg = "This is a user message that is definitely longer than fifty characters in total";
      await service.upsert("src-1", {
        messages: [
          { role: "user", content: longMsg },
          { role: "assistant", content: "Sure, here is a long response about that topic." },
        ],
      });

      expect(embedding.embed).toHaveBeenCalledTimes(1);
      expect(embedding.embed).toHaveBeenCalledWith(longMsg);

      const upsertCall = (repo.upsert as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(upsertCall.sourceId).toBe("src-1");
      expect(upsertCall.messages[0].embedding).toEqual(fakeVector);
      expect(upsertCall.messages[1].embedding).toBeNull();
    });

    it("passes metadata through to repository", async () => {
      await service.upsert("src-2", {
        title: "Updated title",
        source: "webui",
        tags: ["imported"],
      });

      const upsertCall = (repo.upsert as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(upsertCall.sourceId).toBe("src-2");
      expect(upsertCall.title).toBe("Updated title");
      expect(upsertCall.source).toBe("webui");
      expect(upsertCall.tags).toEqual(["imported"]);
    });

    it("does not embed when no messages provided", async () => {
      await service.upsert("src-3");

      expect(embedding.embed).not.toHaveBeenCalled();

      const upsertCall = (repo.upsert as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(upsertCall.sourceId).toBe("src-3");
      expect(upsertCall.messages).toBeUndefined();
    });

    it("skips embedding for short user messages", async () => {
      await service.upsert("src-4", {
        messages: [{ role: "user", content: "Hi" }],
      });

      expect(embedding.embed).not.toHaveBeenCalled();
      const upsertCall = (repo.upsert as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(upsertCall.messages[0].embedding).toBeNull();
    });
  });

  describe("search", () => {
    it("embeds query and uses vector search when embedding succeeds", async () => {
      await service.search("search query", ["tag"], 5);

      expect(embedding.embed).toHaveBeenCalledWith("search query");
      expect(repo.search).toHaveBeenCalledWith({
        query: "search query",
        tags: ["tag"],
        queryEmbedding: fakeVector,
        limit: 5,
        include: undefined,
      });
    });

    it("falls back to text search when embedding returns null", async () => {
      embedding = createMockEmbedding(null);
      service = new ConversationService(repo, embedding);

      await service.search("search query", ["tag"]);

      expect(embedding.embed).toHaveBeenCalledWith("search query");
      expect(repo.search).toHaveBeenCalledWith({
        query: "search query",
        tags: ["tag"],
        limit: undefined,
        include: undefined,
      });
    });

    it("uses text search when no query is provided", async () => {
      await service.search(undefined, ["tag"]);

      expect(embedding.embed).not.toHaveBeenCalled();
      expect(repo.search).toHaveBeenCalledWith({
        query: undefined,
        tags: ["tag"],
        limit: undefined,
        include: undefined,
      });
    });

    it("forwards include parameter to repository", async () => {
      await service.search("test", undefined, undefined, ["avg_embedding"]);

      expect(repo.search).toHaveBeenCalledWith(
        expect.objectContaining({ include: ["avg_embedding"] }),
      );
    });

    it("forwards centroids in include parameter to repository", async () => {
      await service.search("test", undefined, undefined, ["avg_embedding", "centroids"]);

      expect(repo.search).toHaveBeenCalledWith(
        expect.objectContaining({ include: ["avg_embedding", "centroids"] }),
      );
    });
  });

  describe("getById", () => {
    it("delegates to repository", async () => {
      const result = await service.getById("conv-1");
      expect(repo.getById).toHaveBeenCalledWith("conv-1");
      expect(result).toEqual(mockConversation);
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
