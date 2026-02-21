import type { Conversation } from "../types/conversation.js";
import type { ConversationRepository } from "../repository/conversation-types.js";
import type { EmbeddingService } from "../embedding/types.js";

const MIN_EMBED_LENGTH = 50;

export class ConversationService {
  constructor(
    private repository: ConversationRepository,
    private embedding: EmbeddingService,
  ) {}

  async initialize(): Promise<void> {
    await this.repository.initialize();
  }

  async store(
    title: string,
    messages: { role: string; content: string }[],
    options: { source?: string; sourceId?: string; tags?: string[]; userId?: string | null } = {},
  ): Promise<Conversation> {
    const embeddedMessages = await Promise.all(
      messages.map(async (msg) => {
        let embedding: number[] | null = null;

        if (msg.role === "user" && msg.content.length >= MIN_EMBED_LENGTH) {
          embedding = await this.embedding.embed(msg.content);
        }

        return { role: msg.role, content: msg.content, embedding };
      }),
    );

    return this.repository.store({
      title,
      source: options.source ?? "",
      sourceId: options.sourceId,
      userId: options.userId,
      tags: options.tags ?? [],
      messages: embeddedMessages,
    });
  }

  async upsert(
    sourceId: string,
    options: {
      title?: string;
      source?: string;
      tags?: string[];
      userId?: string | null;
      messages?: { role: string; content: string }[];
    } = {},
  ): Promise<Conversation> {
    let embeddedMessages:
      | { role: string; content: string; embedding: number[] | null }[]
      | undefined;

    if (options.messages && options.messages.length > 0) {
      embeddedMessages = await Promise.all(
        options.messages.map(async (msg) => {
          let embedding: number[] | null = null;

          if (msg.role === "user" && msg.content.length >= MIN_EMBED_LENGTH) {
            embedding = await this.embedding.embed(msg.content);
          }

          return { role: msg.role, content: msg.content, embedding };
        }),
      );
    }

    return this.repository.upsert({
      sourceId,
      userId: options.userId,
      title: options.title,
      source: options.source,
      tags: options.tags,
      messages: embeddedMessages,
    });
  }

  async search(
    query?: string,
    tags?: string[],
    limit?: number,
    include?: string[],
    userId?: string | null,
  ): Promise<Conversation[]> {
    let queryEmbedding: number[] | null = null;

    if (query) {
      queryEmbedding = await this.embedding.embed(query);
    }

    if (queryEmbedding) {
      return this.repository.search({ query, tags, userId, queryEmbedding, limit, include });
    }

    return this.repository.search({ query, tags, userId, limit, include });
  }

  async getById(id: string): Promise<Conversation | null> {
    return this.repository.getById(id);
  }

  async healthCheck(): Promise<boolean> {
    return this.repository.healthCheck();
  }

  async close(): Promise<void> {
    await this.repository.close();
  }
}
