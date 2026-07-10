import Fastify from "fastify";
import type { MemoryService } from "./services/memory-service.js";
import type { ConversationService } from "./services/conversation-service.js";
import type { RecallService } from "./services/recall-service.js";
import { memoryRoutes } from "./routes/memories.js";
import { conversationRoutes } from "./routes/conversations.js";
import { recallRoutes } from "./routes/recall.js";
import { chatMemoryRoutes } from "./routes/chat-memory.js";

export interface AppOptions {
  service: MemoryService;
  conversationService?: ConversationService;
  recallService?: RecallService;
  databaseUrl?: string;
}

export function buildApp(options: AppOptions) {
  const { service, conversationService, recallService, databaseUrl } = options;
  const app = Fastify({ logger: false });

  app.get("/health", async (_request, reply) => {
    const healthy = await service.healthCheck();
    if (!healthy) {
      return reply.status(503).send({ status: "unhealthy" });
    }
    return { status: "ok" };
  });

  app.register(memoryRoutes(service));

  if (conversationService) {
    app.register(conversationRoutes(conversationService));
  }

  if (recallService) {
    app.register(recallRoutes(recallService));
  }

  if (databaseUrl) {
    app.register(chatMemoryRoutes(databaseUrl));
  }

  app.addHook("onClose", async () => {
    await service.close();
    if (conversationService) {
      await conversationService.close();
    }
  });

  return app;
}
