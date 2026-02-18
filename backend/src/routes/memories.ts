import type { FastifyInstance } from "fastify";
import type { MemoryService } from "../services/memory-service.js";
import type {
  StoreMemoryRequest,
  FetchMemoriesQuery,
} from "../types/memory.js";

export function memoryRoutes(service: MemoryService) {
  return async function (app: FastifyInstance): Promise<void> {
    app.post<{ Body: StoreMemoryRequest }>(
      "/api/memories",
      async (request, reply) => {
        const { content, tags } = request.body ?? {};

        if (!content || typeof content !== "string" || content.trim() === "") {
          return reply.status(400).send({
            error: "content is required and must be a non-empty string",
          });
        }

        const memory = await service.store(
          content.trim(),
          Array.isArray(tags) ? tags : [],
        );

        return reply.status(201).send(memory);
      },
    );

    app.get<{ Querystring: FetchMemoriesQuery }>(
      "/api/memories",
      async (request) => {
        const { query, tags } = request.query;

        const tagList = tags
          ? tags.split(",").map((t) => t.trim().toLowerCase())
          : undefined;

        const memories = await service.fetch(query, tagList);
        return { memories, total: memories.length };
      },
    );
  };
}
