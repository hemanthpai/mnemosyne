import type { FastifyInstance } from "fastify";
import type { RecallService } from "../services/recall-service.js";

export function recallRoutes(service: RecallService) {
  return async function (app: FastifyInstance): Promise<void> {
    app.post<{ Body: { query: string; userId?: string } }>(
      "/api/recall",
      async (request, reply) => {
        const { query, userId } = request.body ?? {};

        if (!query || typeof query !== "string" || query.trim() === "") {
          return reply.status(400).send({
            error: "query is required and must be a non-empty string",
          });
        }

        const result = await service.recall(query.trim(), userId || undefined);
        return result;
      },
    );
  };
}
