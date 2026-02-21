import pg from "pg";
import type { Conversation, ConversationMessage } from "../types/conversation.js";
import type {
  ConversationRepository,
  StoreConversationParams,
  UpsertConversationParams,
  SearchConversationParams,
} from "./conversation-types.js";
import { kMeans } from "../utils/kmeans.js";

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

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'conversations' AND column_name = 'avg_embedding'
  ) THEN
    ALTER TABLE conversations ADD COLUMN avg_embedding vector(4096);
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS conversation_centroids (
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  idx INTEGER NOT NULL,
  embedding vector(4096) NOT NULL,
  PRIMARY KEY (conversation_id, idx)
);
CREATE INDEX IF NOT EXISTS idx_conv_centroids_conv_id ON conversation_centroids(conversation_id);

ALTER TABLE conversations ADD COLUMN IF NOT EXISTS user_id TEXT;
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
`;

export class ConversationPostgresRepository implements ConversationRepository {
  private pool: pg.Pool;

  constructor(connectionString: string) {
    this.pool = new pg.Pool({ connectionString });
  }

  async initialize(): Promise<void> {
    await this.pool.query(SCHEMA_SQL);
    await this.backfillAvgEmbeddings();
    await this.backfillCentroids();
  }

  private async backfillAvgEmbeddings(): Promise<void> {
    const result = await this.pool.query(
      `SELECT DISTINCT c.id
       FROM conversations c
       JOIN conversation_messages cm ON cm.conversation_id = c.id
       WHERE c.avg_embedding IS NULL AND cm.embedding IS NOT NULL`,
    );
    for (const row of result.rows) {
      const client = await this.pool.connect();
      try {
        await this.recomputeAvgEmbedding(client, row.id as string);
      } finally {
        client.release();
      }
    }
  }

  private async recomputeAvgEmbedding(
    client: pg.PoolClient,
    conversationId: string,
  ): Promise<void> {
    const result = await client.query(
      `SELECT embedding::text FROM conversation_messages
       WHERE conversation_id = $1 AND embedding IS NOT NULL`,
      [conversationId],
    );

    if (result.rows.length === 0) {
      await client.query(
        `UPDATE conversations SET avg_embedding = NULL WHERE id = $1`,
        [conversationId],
      );
      return;
    }

    const vectors = result.rows.map((r) => JSON.parse(r.embedding as string) as number[]);
    const dim = vectors[0].length;
    const avg = new Array(dim).fill(0);
    for (const vec of vectors) {
      for (let i = 0; i < dim; i++) {
        avg[i] += vec[i];
      }
    }
    for (let i = 0; i < dim; i++) {
      avg[i] /= vectors.length;
    }

    await client.query(
      `UPDATE conversations SET avg_embedding = $1::vector WHERE id = $2`,
      [JSON.stringify(avg), conversationId],
    );
  }

  private async recomputeCentroids(
    client: pg.PoolClient,
    conversationId: string,
  ): Promise<void> {
    const result = await client.query(
      `SELECT embedding::text FROM conversation_messages
       WHERE conversation_id = $1 AND embedding IS NOT NULL`,
      [conversationId],
    );

    // Delete existing centroids
    await client.query(
      `DELETE FROM conversation_centroids WHERE conversation_id = $1`,
      [conversationId],
    );

    if (result.rows.length === 0) return;

    const vectors = result.rows.map(
      (r) => JSON.parse(r.embedding as string) as number[],
    );
    const k = Math.min(3, vectors.length);
    const centroids = kMeans(vectors, k);

    for (let i = 0; i < centroids.length; i++) {
      await client.query(
        `INSERT INTO conversation_centroids (conversation_id, idx, embedding)
         VALUES ($1, $2, $3::vector)`,
        [conversationId, i, JSON.stringify(centroids[i])],
      );
    }
  }

  private async backfillCentroids(): Promise<void> {
    const result = await this.pool.query(
      `SELECT DISTINCT c.id
       FROM conversations c
       JOIN conversation_messages cm ON cm.conversation_id = c.id
       WHERE cm.embedding IS NOT NULL
         AND NOT EXISTS (
           SELECT 1 FROM conversation_centroids cc WHERE cc.conversation_id = c.id
         )`,
    );
    if (result.rows.length === 0) return;

    const client = await this.pool.connect();
    try {
      for (const row of result.rows) {
        await this.recomputeCentroids(client, row.id as string);
      }
    } finally {
      client.release();
    }
  }

  async store(params: StoreConversationParams): Promise<Conversation> {
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");

      const convResult = await client.query(
        `INSERT INTO conversations (title, source, source_id, tags, user_id)
         VALUES ($1, $2, $3, $4, $5)
         RETURNING id, title, source, source_id, user_id, tags, created_at, updated_at`,
        [params.title, params.source, params.sourceId ?? null, params.tags, params.userId ?? null],
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

      await this.recomputeAvgEmbedding(client, conv.id as string);
      await this.recomputeCentroids(client, conv.id as string);
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
          `INSERT INTO conversations (title, source, source_id, tags, user_id)
           VALUES ($1, $2, $3, $4, $5)
           RETURNING id`,
          [
            params.title ?? "",
            params.source ?? "",
            params.sourceId,
            params.tags ?? [],
            params.userId ?? null,
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
        if (params.userId !== undefined) {
          updates.push(`user_id = $${idx}`);
          values.push(params.userId);
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

      await this.recomputeAvgEmbedding(client, conversationId);
      await this.recomputeCentroids(client, conversationId);
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

  private shouldIncludeAvgEmbedding(include?: string[]): boolean {
    return include?.includes("avg_embedding") ?? false;
  }

  private shouldIncludeCentroids(include?: string[]): boolean {
    return include?.includes("centroids") ?? false;
  }

  private async vectorSearch(
    params: SearchConversationParams,
    limit: number,
  ): Promise<Conversation[]> {
    const conditions: string[] = [];
    const values: unknown[] = [
      JSON.stringify(params.queryEmbedding),
      limit,
    ];
    let nextIdx = 3;

    if (params.tags && params.tags.length > 0) {
      conditions.push(`AND c.tags && $${nextIdx}`);
      values.push(params.tags);
      nextIdx++;
    }

    if (params.userId) {
      conditions.push(`AND c.user_id = $${nextIdx}`);
      values.push(params.userId);
      nextIdx++;
    }

    const extraConditions = conditions.join(" ");

    const result = await this.pool.query(
      `WITH ranked AS (
        SELECT cm.conversation_id,
               MIN(cm.embedding <=> $1::vector) AS best_distance
        FROM conversation_messages cm
        JOIN conversations c ON c.id = cm.conversation_id
        WHERE cm.embedding IS NOT NULL ${extraConditions}
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

    const conversations = await this.fetchConversationsByIds(ids, params.include);

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

    if (params.userId) {
      conditions.push(`c.user_id = $${idx}`);
      values.push(params.userId);
      idx++;
    }

    const where =
      conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";

    values.push(limit);

    const result = await this.pool.query(
      `SELECT c.id, c.title, c.source, c.source_id, c.user_id, c.tags, c.created_at, c.updated_at
       FROM conversations c
       ${where}
       ORDER BY c.created_at DESC
       LIMIT $${idx}`,
      values,
    );

    if (result.rows.length === 0) return [];

    const ids = result.rows.map((r) => r.id);
    return this.fetchConversationsByIds(ids, params.include);
  }

  async getById(id: string): Promise<Conversation | null> {
    const convResult = await this.pool.query(
      `SELECT id, title, source, source_id, user_id, tags, created_at, updated_at
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

  private async fetchConversationsByIds(
    ids: string[],
    include?: string[],
  ): Promise<Conversation[]> {
    if (ids.length === 0) return [];

    const placeholders = ids.map((_, i) => `$${i + 1}`).join(", ");
    const extraCols = this.shouldIncludeAvgEmbedding(include)
      ? ", avg_embedding"
      : "";

    const convResult = await this.pool.query(
      `SELECT id, title, source, source_id, user_id, tags, created_at, updated_at${extraCols}
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

    // Optionally fetch centroids
    let centroidsByConv: Map<string, number[][]> | null = null;
    if (this.shouldIncludeCentroids(include)) {
      const centroidResult = await this.pool.query(
        `SELECT conversation_id, idx, embedding::text
         FROM conversation_centroids
         WHERE conversation_id IN (${placeholders})
         ORDER BY conversation_id, idx`,
        ids,
      );
      centroidsByConv = new Map();
      for (const row of centroidResult.rows) {
        const convId = row.conversation_id as string;
        const embedding = JSON.parse(row.embedding as string) as number[];
        const existing = centroidsByConv.get(convId) ?? [];
        existing.push(embedding);
        centroidsByConv.set(convId, existing);
      }
    }

    return convResult.rows.map((row) => {
      const conv: Conversation = {
        ...this.rowToConversation(row),
        messages: msgsByConv.get(row.id as string) ?? [],
      };
      if (centroidsByConv) {
        conv.centroids = centroidsByConv.get(row.id as string) ?? null;
      }
      return conv;
    });
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
      userId: (row.user_id as string | null) ?? null,
      tags: row.tags as string[],
      createdAt: (row.created_at as Date).toISOString(),
      updatedAt: (row.updated_at as Date).toISOString(),
    };
    if (row.score != null) {
      conv.score = parseFloat(row.score as string);
    }
    if (row.avg_embedding != null) {
      conv.avgEmbedding = JSON.parse(row.avg_embedding as string) as number[];
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
