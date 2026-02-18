import pg from "pg";
import type { Memory } from "../types/memory.js";
import type { MemoryRepository, StoreParams, FetchParams } from "./types.js";

const SCHEMA_SQL = `
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content TEXT NOT NULL,
  tags TEXT[] NOT NULL DEFAULT '{}',
  embedding vector(4096),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memories_tags ON memories USING GIN (tags);
`;

const MIGRATION_SQL = `
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'memories' AND column_name = 'embedding'
  ) THEN
    ALTER TABLE memories ALTER COLUMN embedding TYPE vector(4096);
  END IF;
END $$;
`;

export class PostgresRepository implements MemoryRepository {
  private pool: pg.Pool;

  constructor(connectionString: string) {
    this.pool = new pg.Pool({ connectionString });
  }

  async initialize(): Promise<void> {
    await this.pool.query(MIGRATION_SQL);
    await this.pool.query(SCHEMA_SQL);
  }

  async store(params: StoreParams): Promise<Memory> {
    const hasEmbedding = params.embedding && params.embedding.length > 0;

    const result = hasEmbedding
      ? await this.pool.query(
          `INSERT INTO memories (content, tags, embedding)
           VALUES ($1, $2, $3::vector)
           RETURNING id, content, tags, created_at, updated_at`,
          [params.content, params.tags, JSON.stringify(params.embedding)],
        )
      : await this.pool.query(
          `INSERT INTO memories (content, tags)
           VALUES ($1, $2)
           RETURNING id, content, tags, created_at, updated_at`,
          [params.content, params.tags],
        );

    return this.rowToMemory(result.rows[0]);
  }

  async fetch(params: FetchParams): Promise<Memory[]> {
    const limit = params.limit ?? 50;

    // Vector search path: when we have a query embedding
    if (params.queryEmbedding && params.queryEmbedding.length > 0) {
      return this.vectorSearch(params, limit);
    }

    // Text search path: ILIKE fallback
    return this.textSearch(params, limit);
  }

  private async vectorSearch(params: FetchParams, limit: number): Promise<Memory[]> {
    const conditions: string[] = [];
    const values: unknown[] = [JSON.stringify(params.queryEmbedding)];
    let idx = 2;

    if (params.tags && params.tags.length > 0) {
      conditions.push(`tags && $${idx}`);
      values.push(params.tags);
      idx++;
    }

    const where = conditions.length > 0
      ? `WHERE ${conditions.join(" AND ")}`
      : "";

    values.push(limit);

    const result = await this.pool.query(
      `SELECT id, content, tags, created_at, updated_at,
              1 - (embedding <=> $1::vector) AS score
       FROM memories
       ${where}
       ORDER BY embedding <=> $1::vector
       LIMIT $${idx}`,
      values,
    );

    return result.rows.map((row) => this.rowToMemory(row));
  }

  private async textSearch(params: FetchParams, limit: number): Promise<Memory[]> {
    const conditions: string[] = [];
    const values: unknown[] = [];
    let idx = 1;

    if (params.query) {
      conditions.push(`content ILIKE $${idx}`);
      values.push(`%${params.query}%`);
      idx++;
    }

    if (params.tags && params.tags.length > 0) {
      conditions.push(`tags && $${idx}`);
      values.push(params.tags);
      idx++;
    }

    const where = conditions.length > 0
      ? `WHERE ${conditions.join(" AND ")}`
      : "";

    values.push(limit);

    const result = await this.pool.query(
      `SELECT id, content, tags, created_at, updated_at
       FROM memories ${where}
       ORDER BY created_at DESC
       LIMIT $${idx}`,
      values,
    );

    return result.rows.map((row) => this.rowToMemory(row));
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

  private rowToMemory(row: Record<string, unknown>): Memory {
    const memory: Memory = {
      id: row.id as string,
      content: row.content as string,
      tags: row.tags as string[],
      createdAt: (row.created_at as Date).toISOString(),
      updatedAt: (row.updated_at as Date).toISOString(),
    };
    if (row.score != null) {
      memory.score = parseFloat(row.score as string);
    }
    return memory;
  }
}
