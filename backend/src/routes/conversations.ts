import type { FastifyInstance } from "fastify";
import type { ConversationService } from "../services/conversation-service.js";
import type {
  StoreConversationRequest,
  SearchConversationsQuery,
} from "../types/conversation.js";

export function conversationRoutes(service: ConversationService) {
  return async function (app: FastifyInstance): Promise<void> {
    app.post<{ Body: StoreConversationRequest }>(
      "/api/conversations",
      async (request, reply) => {
        const { title, source, sourceId, tags, messages } =
          request.body ?? {};

        if (!title || typeof title !== "string" || title.trim() === "") {
          return reply.status(400).send({
            error: "title is required and must be a non-empty string",
          });
        }

        if (!Array.isArray(messages) || messages.length === 0) {
          return reply.status(400).send({
            error: "messages is required and must be a non-empty array",
          });
        }

        for (const msg of messages) {
          if (
            !msg.role ||
            typeof msg.role !== "string" ||
            !msg.content ||
            typeof msg.content !== "string"
          ) {
            return reply.status(400).send({
              error:
                "each message must have a non-empty role and content string",
            });
          }
        }

        const conversation = await service.store(title.trim(), messages, {
          source: source ?? "",
          sourceId: sourceId,
          tags: Array.isArray(tags) ? tags : [],
        });

        return reply.status(201).send(conversation);
      },
    );

    app.get<{ Querystring: SearchConversationsQuery }>(
      "/api/conversations",
      async (request) => {
        const { query, tags, limit } = request.query;

        const tagList = tags
          ? tags.split(",").map((t) => t.trim().toLowerCase())
          : undefined;

        const parsedLimit = limit ? parseInt(limit, 10) : undefined;

        const conversations = await service.search(
          query,
          tagList,
          parsedLimit,
        );
        return { conversations, total: conversations.length };
      },
    );

    app.get<{ Params: { id: string } }>(
      "/api/conversations/:id",
      async (request, reply) => {
        const { id } = request.params;
        const conversation = await service.getById(id);

        if (!conversation) {
          return reply.status(404).send({ error: "conversation not found" });
        }

        return conversation;
      },
    );
  };
}
