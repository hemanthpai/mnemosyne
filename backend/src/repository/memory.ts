import { randomUUID } from "node:crypto";
import type { Memory } from "../types/memory.js";
import type { MemoryRepository, StoreParams, FetchParams } from "./types.js";

export class InMemoryRepository implements MemoryRepository {
  private memories: Memory[] = [];

  async initialize(): Promise<void> {}

  async store(params: StoreParams): Promise<Memory> {
    const now = new Date().toISOString();
    const memory: Memory = {
      id: randomUUID(),
      content: params.content,
      tags: params.tags,
      createdAt: now,
      updatedAt: now,
    };
    this.memories.push(memory);
    return memory;
  }

  async fetch(params: FetchParams): Promise<Memory[]> {
    let result = this.memories;

    if (params.query) {
      const lower = params.query.toLowerCase();
      result = result.filter((m) =>
        m.content.toLowerCase().includes(lower),
      );
    }

    if (params.tags && params.tags.length > 0) {
      result = result.filter((m) =>
        params.tags!.some((tag) =>
          m.tags.map((t) => t.toLowerCase()).includes(tag.toLowerCase()),
        ),
      );
    }

    return result;
  }

  async healthCheck(): Promise<boolean> {
    return true;
  }

  async close(): Promise<void> {}

  clear(): void {
    this.memories = [];
  }
}
