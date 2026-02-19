import pg from "pg";
import type { Conversation, ConversationMessage } from "../types/conversation.js";
import type {
  ConversationRepository,
  StoreConversationParams,
  UpsertConversationParams,
  SearchConversationParams,
} from "./conversation-types.js";

const SCHEMA_SQL = `
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT '',
  source_id TEXT,
  tags TEXT[] NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversation_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  position INTEGER NOT NULL,
  embedding vector(4096),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversations_tags ON conversations USING GIN (tags);
DROP INDEX IF EXISTS idx_conversations_source_id;
CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_source_id_unique ON conversations (source_id) WHERE source_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_conv_messages_conversation_id ON conversation_messages (conversation_id);
`;

export class ConversationPostgresRepository implements ConversationRepository {
  private pool: pg.Pool;

  constructor(connectionString: string) {
    this.pool = new pg.Pool({ connectionString });
  }

  async initialize(): Promise<void> {
    await this.pool.query(SCHEMA_SQL);
  }

  async store(params: StoreConversationParams): Promise<Conversation> {
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");

      const convResult = await client.query(
        `INSERT INTO conversations (title, source, source_id, tags)
         VALUES ($1, $2, $3, $4)
         RETURNING id, title, source, source_id, tags, created_at, updated_at`,
        [params.title, params.source, params.sourceId ?? null, params.tags],
      );

      const conv = convResult.rows[0];
      const messages: ConversationMessage[] = [];

      for (let i = 0; i < params.messages.length; i++) {
        const msg = params.messages[i];
        const hasEmbedding = msg.embedding && msg.embedding.length > 0;

        const msgResult = hasEmbedding
          ? await client.query(
              `INSERT INTO conversation_messages (conversation_id, role, content, position, embedding)
               VALUES ($1, $2, $3, $4, $5::vector)
               RETURNING id, conversation_id, role, content, position, created_at`,
              [conv.id, msg.role, msg.content, i, JSON.stringify(msg.embedding)],
            )
          : await client.query(
              `INSERT INTO conversation_messages (conversation_id, role, content, position)
               VALUES ($1, $2, $3, $4)
               RETURNING id, conversation_id, role, content, position, created_at`,
              [conv.id, msg.role, msg.content, i],
            );

        messages.push(this.rowToMessage(msgResult.rows[0]));
      }

      await client.query("COMMIT");

      return {
        ...this.rowToConversation(conv),
        messages,
      };
    } catch (err) {
      await client.query("ROLLBACK");
      throw err;
    } finally {
      client.release();
    }
  }

  async findBySourceId(sourceId: string): Promise<Conversation | null> {
    const result = await this.pool.query(
      `SELECT id FROM conversations WHERE source_id = $1`,
      [sourceId],
    );
    if (result.rows.length === 0) return null;
    return this.getById(result.rows[0].id as string);
  }

  async upsert(params: UpsertConversationParams): Promise<Conversation> {
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");

      // Find existing conversation by source_id
      const existing = await client.query(
        `SELECT id FROM conversations WHERE source_id = $1`,
        [params.sourceId],
      );

      let conversationId: string;

      if (existing.rows.length === 0) {
        // Create new conversation
        const insertResult = await client.query(
          `INSERT INTO conversations (title, source, source_id, tags)
           VALUES ($1, $2, $3, $4)
           RETURNING id`,
          [
            params.title ?? "",
            params.source ?? "",
            params.sourceId,
            params.tags ?? [],
          ],
        );
        conversationId = insertResult.rows[0].id as string;
      } else {
        conversationId = existing.rows[0].id as string;

        // Update metadata fields that are present
        const updates: string[] = [];
        const values: unknown[] = [];
        let idx = 1;

        if (params.title !== undefined) {
          updates.push(`title = $${idx}`);
          values.push(params.title);
          idx++;
        }
        if (params.source !== undefined) {
          updates.push(`source = $${idx}`);
          values.push(params.source);
          idx++;
        }
        if (params.tags !== undefined) {
          updates.push(`tags = $${idx}`);
          values.push(params.tags);
          idx++;
        }

        if (updates.length > 0) {
          updates.push(`updated_at = now()`);
          values.push(conversationId);
          await client.query(
            `UPDATE conversations SET ${updates.join(", ")} WHERE id = $${idx}`,
            values,
          );
        }
      }

      // Append new messages if provided
      if (params.messages && params.messages.length > 0) {
        // Get the next position
        const maxPos = await client.query(
          `SELECT COALESCE(MAX(position), -1) AS max_pos FROM conversation_messages WHERE conversation_id = $1`,
          [conversationId],
        );
        let nextPosition = (maxPos.rows[0].max_pos as number) + 1;

        for (const msg of params.messages) {
          const hasEmbedding = msg.embedding && msg.embedding.length > 0;

          if (hasEmbedding) {
            await client.query(
              `INSERT INTO conversation_messages (conversation_id, role, content, position, embedding)
               VALUES ($1, $2, $3, $4, $5::vector)`,
              [conversationId, msg.role, msg.content, nextPosition, JSON.stringify(msg.embedding)],
            );
          } else {
            await client.query(
              `INSERT INTO conversation_messages (conversation_id, role, content, position)
               VALUES ($1, $2, $3, $4)`,
              [conversationId, msg.role, msg.content, nextPosition],
            );
          }
          nextPosition++;
        }

        // Update updated_at when messages are appended
        await client.query(
          `UPDATE conversations SET updated_at = now() WHERE id = $1`,
          [conversationId],
        );
      }

      await client.query("COMMIT");

      return (await this.getById(conversationId))!;
    } catch (err) {
      await client.query("ROLLBACK");
      throw err;
    } finally {
      client.release();
    }
  }

  async search(params: SearchConversationParams): Promise<Conversation[]> {
    const limit = params.limit ?? 10;

    if (params.queryEmbedding && params.queryEmbedding.length > 0) {
      return this.vectorSearch(params, limit);
    }

    return this.textSearch(params, limit);
  }

  private async vectorSearch(
    params: SearchConversationParams,
    limit: number,
  ): Promise<Conversation[]> {
    const tagCondition =
      params.tags && params.tags.length > 0
        ? `AND c.tags && $3`
        : "";

    const values: unknown[] = [
      JSON.stringify(params.queryEmbedding),
      limit,
    ];
    if (params.tags && params.tags.length > 0) {
      values.push(params.tags);
    }

    const result = await this.pool.query(
      `WITH ranked AS (
        SELECT cm.conversation_id,
               MIN(cm.embedding <=> $1::vector) AS best_distance
        FROM conversation_messages cm
        JOIN conversations c ON c.id = cm.conversation_id
        WHERE cm.embedding IS NOT NULL ${tagCondition}
        GROUP BY cm.conversation_id
        ORDER BY best_distance ASC
        LIMIT $2
      )
      SELECT conversation_id, 1 - best_distance AS score FROM ranked`,
      values,
    );

    if (result.rows.length === 0) return [];

    const ids = result.rows.map((r) => r.conversation_id);
    const scoreMap = new Map(
      result.rows.map((r) => [
        r.conversation_id,
        parseFloat(r.score as string),
      ]),
    );

    const conversations = await this.fetchConversationsByIds(ids);

    return conversations
      .map((c) => ({ ...c, score: scoreMap.get(c.id) }))
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  }

  private async textSearch(
    params: SearchConversationParams,
    limit: number,
  ): Promise<Conversation[]> {
    const conditions: string[] = [];
    const values: unknown[] = [];
    let idx = 1;

    if (params.query) {
      conditions.push(
        `(c.id IN (
          SELECT cm.conversation_id FROM conversation_messages cm
          WHERE cm.content ILIKE $${idx}
        ) OR c.title ILIKE $${idx})`,
      );
      values.push(`%${params.query}%`);
      idx++;
    }

    if (params.tags && params.tags.length > 0) {
      conditions.push(`c.tags && $${idx}`);
      values.push(params.tags);
      idx++;
    }

    const where =
      conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";

    values.push(limit);

    const result = await this.pool.query(
      `SELECT c.id, c.title, c.source, c.source_id, c.tags, c.created_at, c.updated_at
       FROM conversations c
       ${where}
       ORDER BY c.created_at DESC
       LIMIT $${idx}`,
      values,
    );

    if (result.rows.length === 0) return [];

    const ids = result.rows.map((r) => r.id);
    return this.fetchConversationsByIds(ids);
  }

  async getById(id: string): Promise<Conversation | null> {
    const convResult = await this.pool.query(
      `SELECT id, title, source, source_id, tags, created_at, updated_at
       FROM conversations WHERE id = $1`,
      [id],
    );

    if (convResult.rows.length === 0) return null;

    const msgResult = await this.pool.query(
      `SELECT id, conversation_id, role, content, position, created_at
       FROM conversation_messages
       WHERE conversation_id = $1
       ORDER BY position ASC`,
      [id],
    );

    return {
      ...this.rowToConversation(convResult.rows[0]),
      messages: msgResult.rows.map((r) => this.rowToMessage(r)),
    };
  }

  private async fetchConversationsByIds(ids: string[]): Promise<Conversation[]> {
    if (ids.length === 0) return [];

    const placeholders = ids.map((_, i) => `$${i + 1}`).join(", ");

    const convResult = await this.pool.query(
      `SELECT id, title, source, source_id, tags, created_at, updated_at
       FROM conversations WHERE id IN (${placeholders})`,
      ids,
    );

    const msgResult = await this.pool.query(
      `SELECT id, conversation_id, role, content, position, created_at
       FROM conversation_messages
       WHERE conversation_id IN (${placeholders})
       ORDER BY position ASC`,
      ids,
    );

    const msgsByConv = new Map<string, ConversationMessage[]>();
    for (const row of msgResult.rows) {
      const msg = this.rowToMessage(row);
      const existing = msgsByConv.get(msg.conversationId) ?? [];
      existing.push(msg);
      msgsByConv.set(msg.conversationId, existing);
    }

    return convResult.rows.map((row) => ({
      ...this.rowToConversation(row),
      messages: msgsByConv.get(row.id as string) ?? [],
    }));
  }

  async healthCheck(): Promise<boolean> {
    try {
      await this.pool.query("SELECT 1");
      return true;
    } catch {
      return false;
    }
  }

  async close(): Promise<void> {
    await this.pool.end();
  }

  private rowToConversation(row: Record<string, unknown>): Conversation {
    const conv: Conversation = {
      id: row.id as string,
      title: row.title as string,
      source: row.source as string,
      sourceId: row.source_id as string | undefined,
      tags: row.tags as string[],
      createdAt: (row.created_at as Date).toISOString(),
      updatedAt: (row.updated_at as Date).toISOString(),
    };
    if (row.score != null) {
      conv.score = parseFloat(row.score as string);
    }
    return conv;
  }

  private rowToMessage(row: Record<string, unknown>): ConversationMessage {
    return {
      id: row.id as string,
      conversationId: row.conversation_id as string,
      role: row.role as string,
      content: row.content as string,
      position: row.position as number,
      createdAt: (row.created_at as Date).toISOString(),
    };
  }
}
