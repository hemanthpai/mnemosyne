import type { Memory } from "../types/memory.js";

export interface StoreParams {
  content: string;
  tags: string[];
}

export interface FetchParams {
  query?: string;
  tags?: string[];
}

export interface MemoryRepository {
  initialize(): Promise<void>;
  store(params: StoreParams): Promise<Memory>;
  fetch(params: FetchParams): Promise<Memory[]>;
  healthCheck(): Promise<boolean>;
  close(): Promise<void>;
}
