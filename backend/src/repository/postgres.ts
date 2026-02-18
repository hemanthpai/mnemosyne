import pg from "pg";
import type { Memory } from "../types/memory.js";
import type { MemoryRepository, StoreParams, FetchParams } from "./types.js";

const SCHEMA_SQL = `
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content TEXT NOT NULL,
  tags TEXT[] NOT NULL DEFAULT '{}',
  embedding vector(1024),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memories_tags ON memories USING GIN (tags);
`;

export class PostgresRepository implements MemoryRepository {
  private pool: pg.Pool;

  constructor(connectionString: string) {
    this.pool = new pg.Pool({ connectionString });
  }

  async initialize(): Promise<void> {
    await this.pool.query(SCHEMA_SQL);
  }

  async store(params: StoreParams): Promise<Memory> {
    const result = await this.pool.query(
      `INSERT INTO memories (content, tags)
       VALUES ($1, $2)
       RETURNING id, content, tags, created_at, updated_at`,
      [params.content, params.tags],
    );
    const row = result.rows[0];
    return this.rowToMemory(row);
  }

  async fetch(params: FetchParams): Promise<Memory[]> {
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

    const result = await this.pool.query(
      `SELECT id, content, tags, created_at, updated_at
       FROM memories ${where}
       ORDER BY created_at DESC`,
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
    return {
      id: row.id as string,
      content: row.content as string,
      tags: row.tags as string[],
      createdAt: (row.created_at as Date).toISOString(),
      updatedAt: (row.updated_at as Date).toISOString(),
    };
  }
}
