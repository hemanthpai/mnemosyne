import Fastify from "fastify";
import type { MemoryRepository } from "./repository/index.js";
import { memoryRoutes } from "./routes/memories.js";

export interface AppOptions {
  repository: MemoryRepository;
}

export function buildApp(options: AppOptions) {
  const { repository } = options;
  const app = Fastify({ logger: false });

  app.get("/health", async (_request, reply) => {
    const healthy = await repository.healthCheck();
    if (!healthy) {
      return reply.status(503).send({ status: "unhealthy" });
    }
    return { status: "ok" };
  });

  app.register(memoryRoutes(repository));

  app.addHook("onClose", async () => {
    await repository.close();
  });

  return app;
}
