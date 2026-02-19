import type { Conversation } from "../types/conversation.js";

export interface StoreConversationParams {
  title: string;
  source: string;
  sourceId?: string;
  tags: string[];
  messages: {
    role: string;
    content: string;
    embedding?: number[] | null;
  }[];
}

export interface UpsertConversationParams {
  sourceId: string;
  title?: string;
  source?: string;
  tags?: string[];
  messages?: {
    role: string;
    content: string;
    embedding?: number[] | null;
  }[];
}

export interface SearchConversationParams {
  query?: string;
  tags?: string[];
  queryEmbedding?: number[] | null;
  limit?: number;
}

export interface ConversationRepository {
  initialize(): Promise<void>;
  store(params: StoreConversationParams): Promise<Conversation>;
  search(params: SearchConversationParams): Promise<Conversation[]>;
  getById(id: string): Promise<Conversation | null>;
  findBySourceId(sourceId: string): Promise<Conversation | null>;
  upsert(params: UpsertConversationParams): Promise<Conversation>;
  healthCheck(): Promise<boolean>;
  close(): Promise<void>;
}
