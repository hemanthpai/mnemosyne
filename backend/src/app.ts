import Fastify from "fastify";
import { memoryRoutes } from "./routes/memories.js";

export function buildApp() {
  const app = Fastify({ logger: false });

  app.get("/health", async () => {
    return { status: "ok" };
  });

  app.register(memoryRoutes);

  return app;
}
