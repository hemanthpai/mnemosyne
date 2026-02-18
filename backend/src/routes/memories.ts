import { randomUUID } from "node:crypto";
import type { FastifyInstance } from "fastify";
import type {
  Memory,
  StoreMemoryRequest,
  FetchMemoriesQuery,
} from "../types/memory.js";

const memories: Memory[] = [];

export function getMemoryStore(): Memory[] {
  return memories;
}

export function clearMemoryStore(): void {
  memories.length = 0;
}

export async function memoryRoutes(app: FastifyInstance): Promise<void> {
  app.post<{ Body: StoreMemoryRequest }>(
    "/api/memories",
    async (request, reply) => {
      const { content, tags } = request.body ?? {};

      if (!content || typeof content !== "string" || content.trim() === "") {
        return reply.status(400).send({
          error: "content is required and must be a non-empty string",
        });
      }

      const now = new Date().toISOString();
      const memory: Memory = {
        id: randomUUID(),
        content: content.trim(),
        tags: Array.isArray(tags) ? tags : [],
        createdAt: now,
        updatedAt: now,
      };

      memories.push(memory);
      return reply.status(201).send(memory);
    },
  );

  app.get<{ Querystring: FetchMemoriesQuery }>(
    "/api/memories",
    async (request) => {
      const { query, tags } = request.query;
      let result = memories;

      if (query) {
        const lower = query.toLowerCase();
        result = result.filter((m) =>
          m.content.toLowerCase().includes(lower),
        );
      }

      if (tags) {
        const tagList = tags.split(",").map((t) => t.trim().toLowerCase());
        result = result.filter((m) =>
          tagList.some((tag) =>
            m.tags.map((t) => t.toLowerCase()).includes(tag),
          ),
        );
      }

      return { memories: result, total: result.length };
    },
  );
}
