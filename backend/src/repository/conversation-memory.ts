import { randomUUID } from "node:crypto";
import type { Conversation, ConversationMessage } from "../types/conversation.js";
import type {
  ConversationRepository,
  StoreConversationParams,
  UpsertConversationParams,
  SearchConversationParams,
} from "./conversation-types.js";

export class InMemoryConversationRepository implements ConversationRepository {
  private conversations: Conversation[] = [];
  private messages: ConversationMessage[] = [];

  async initialize(): Promise<void> {}

  async store(params: StoreConversationParams): Promise<Conversation> {
    const now = new Date().toISOString();
    const conversationId = randomUUID();

    const conversation: Conversation = {
      id: conversationId,
      title: params.title,
      source: params.source,
      sourceId: params.sourceId,
      tags: params.tags,
      createdAt: now,
      updatedAt: now,
    };

    const storedMessages: ConversationMessage[] = params.messages.map(
      (msg, idx) => ({
        id: randomUUID(),
        conversationId,
        role: msg.role,
        content: msg.content,
        position: idx,
        createdAt: now,
      }),
    );

    this.conversations.push(conversation);
    this.messages.push(...storedMessages);

    return { ...conversation, messages: storedMessages };
  }

  async findBySourceId(sourceId: string): Promise<Conversation | null> {
    const conversation = this.conversations.find((c) => c.sourceId === sourceId);
    if (!conversation) return null;
    return this.getById(conversation.id);
  }

  async upsert(params: UpsertConversationParams): Promise<Conversation> {
    const now = new Date().toISOString();
    let conversation = this.conversations.find((c) => c.sourceId === params.sourceId);

    if (!conversation) {
      // Create new conversation
      conversation = {
        id: randomUUID(),
        title: params.title ?? "",
        source: params.source ?? "",
        sourceId: params.sourceId,
        tags: params.tags ?? [],
        createdAt: now,
        updatedAt: now,
      };
      this.conversations.push(conversation);
    } else {
      // Update metadata fields that are present
      if (params.title !== undefined) conversation.title = params.title;
      if (params.source !== undefined) conversation.source = params.source;
      if (params.tags !== undefined) conversation.tags = params.tags;
      conversation.updatedAt = now;
    }

    // Append new messages if provided
    if (params.messages && params.messages.length > 0) {
      const existingMessages = this.messages.filter(
        (m) => m.conversationId === conversation!.id,
      );
      const nextPosition = existingMessages.length > 0
        ? Math.max(...existingMessages.map((m) => m.position)) + 1
        : 0;

      const newMessages: ConversationMessage[] = params.messages.map(
        (msg, idx) => ({
          id: randomUUID(),
          conversationId: conversation!.id,
          role: msg.role,
          content: msg.content,
          position: nextPosition + idx,
          createdAt: now,
        }),
      );
      this.messages.push(...newMessages);
    }

    return (await this.getById(conversation.id))!;
  }

  async search(params: SearchConversationParams): Promise<Conversation[]> {
    let result = this.conversations;

    if (params.query) {
      const lower = params.query.toLowerCase();
      const matchingConvIds = new Set(
        this.messages
          .filter((m) => m.content.toLowerCase().includes(lower))
          .map((m) => m.conversationId),
      );
      result = result.filter(
        (c) =>
          matchingConvIds.has(c.id) ||
          c.title.toLowerCase().includes(lower),
      );
    }

    if (params.tags && params.tags.length > 0) {
      result = result.filter((c) =>
        params.tags!.some((tag) =>
          c.tags.map((t) => t.toLowerCase()).includes(tag.toLowerCase()),
        ),
      );
    }

    const limit = params.limit ?? 10;
    return result.slice(0, limit).map((c) => ({
      ...c,
      messages: this.messages
        .filter((m) => m.conversationId === c.id)
        .sort((a, b) => a.position - b.position),
    }));
  }

  async getById(id: string): Promise<Conversation | null> {
    const conversation = this.conversations.find((c) => c.id === id);
    if (!conversation) return null;

    const msgs = this.messages
      .filter((m) => m.conversationId === id)
      .sort((a, b) => a.position - b.position);

    return { ...conversation, messages: msgs };
  }

  async healthCheck(): Promise<boolean> {
    return true;
  }

  async close(): Promise<void> {}

  clear(): void {
    this.conversations = [];
    this.messages = [];
  }
}
