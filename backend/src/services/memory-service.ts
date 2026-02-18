import type { Memory } from "../types/memory.js";
import type { MemoryRepository } from "../repository/types.js";
import type { EmbeddingService } from "../embedding/types.js";

export class MemoryService {
  constructor(
    private repository: MemoryRepository,
    private embedding: EmbeddingService,
  ) {}

  async initialize(): Promise<void> {
    await this.repository.initialize();
  }

  async store(content: string, tags: string[]): Promise<Memory> {
    const vector = await this.embedding.embed(content);
    return this.repository.store({ content, tags, embedding: vector });
  }

  async fetch(query?: string, tags?: string[]): Promise<Memory[]> {
    let queryEmbedding: number[] | null = null;

    if (query) {
      queryEmbedding = await this.embedding.embed(query);
    }

    if (queryEmbedding) {
      // Vector search — pass query too so repo can use it for tag filtering
      return this.repository.fetch({ query, tags, queryEmbedding });
    }

    // Fallback to ILIKE text search
    return this.repository.fetch({ query, tags });
  }

  async healthCheck(): Promise<boolean> {
    return this.repository.healthCheck();
  }

  async close(): Promise<void> {
    await this.repository.close();
  }
}
