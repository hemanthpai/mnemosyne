export interface ConversationMessage {
  id: string;
  conversationId: string;
  role: string;
  content: string;
  position: number;
  createdAt: string;
}

export interface Conversation {
  id: string;
  title: string;
  source: string;
  sourceId?: string;
  tags: string[];
  createdAt: string;
  updatedAt: string;
  score?: number;
  avgEmbedding?: number[] | null;
  centroids?: number[][] | null;
  messages?: ConversationMessage[];
}

export interface StoreConversationRequest {
  sourceId: string;
  title?: string;
  source?: string;
  tags?: string[];
  messages?: { role: string; content: string }[];
}

export interface SearchConversationsQuery {
  query?: string;
  tags?: string;
  limit?: string;
  include?: string;
}
