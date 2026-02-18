import Fastify from "fastify";
import type { MemoryService } from "./services/memory-service.js";
import { memoryRoutes } from "./routes/memories.js";

export interface AppOptions {
  service: MemoryService;
}

export function buildApp(options: AppOptions) {
  const { service } = options;
  const app = Fastify({ logger: false });

  app.get("/health", async (_request, reply) => {
    const healthy = await service.healthCheck();
    if (!healthy) {
      return reply.status(503).send({ status: "unhealthy" });
    }
    return { status: "ok" };
  });

  app.register(memoryRoutes(service));

  app.addHook("onClose", async () => {
    await service.close();
  });

  return app;
}
