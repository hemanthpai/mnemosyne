import type { Memory } from "../types/memory.js";

export interface StoreParams {
  content: string;
  tags: string[];
  embedding?: number[] | null;
}

export interface FetchParams {
  query?: string;
  tags?: string[];
  queryEmbedding?: number[] | null;
  limit?: number;
}

export interface MemoryRepository {
  initialize(): Promise<void>;
  store(params: StoreParams): Promise<Memory>;
  fetch(params: FetchParams): Promise<Memory[]>;
  healthCheck(): Promise<boolean>;
  close(): Promise<void>;
}
