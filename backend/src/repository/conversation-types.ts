import type { Conversation } from "../types/conversation.js";

export interface StoreConversationParams {
  title: string;
  source: string;
  sourceId?: string;
  userId?: string | null;
  tags: string[];
  messages: {
    role: string;
    content: string;
    embedding?: number[] | null;
  }[];
}

export interface UpsertConversationParams {
  sourceId: string;
  userId?: string | null;
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
  userId?: string | null;
  queryEmbedding?: number[] | null;
  limit?: number;
  include?: string[];
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
