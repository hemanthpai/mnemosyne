import { buildApp } from "./app.js";
import { InMemoryRepository, PostgresRepository } from "./repository/index.js";
import { ConversationPostgresRepository } from "./repository/index.js";
import type { MemoryRepository } from "./repository/index.js";
import { OllamaEmbeddingService, NoopEmbeddingService } from "./embedding/index.js";
import type { EmbeddingService } from "./embedding/index.js";
import { MemoryService } from "./services/memory-service.js";
import { ConversationService } from "./services/conversation-service.js";

const HOST = process.env.HOST ?? "0.0.0.0";
const PORT = parseInt(process.env.PORT ?? "3000", 10);
const DATABASE_URL = process.env.DATABASE_URL;
const EMBEDDING_URL = process.env.EMBEDDING_URL;
const EMBEDDING_MODEL = process.env.EMBEDDING_MODEL ?? "qwen3-embedding:8b-q8_0";

let repository: MemoryRepository;

if (DATABASE_URL) {
  console.log("Using PostgreSQL repository");
  repository = new PostgresRepository(DATABASE_URL);
} else {
  console.warn("DATABASE_URL not set — using in-memory repository (data will be lost on restart)");
  repository = new InMemoryRepository();
}

let embedding: EmbeddingService;

if (EMBEDDING_URL) {
  console.log(`Using Ollama embedding service at ${EMBEDDING_URL} (model: ${EMBEDDING_MODEL})`);
  embedding = new OllamaEmbeddingService(EMBEDDING_URL, EMBEDDING_MODEL);
} else {
  console.warn("EMBEDDING_URL not set — embeddings disabled (text search only)");
  embedding = new NoopEmbeddingService();
}

const service = new MemoryService(repository, embedding);
await service.initialize();

let conversationService: ConversationService | undefined;

if (DATABASE_URL) {
  const conversationRepo = new ConversationPostgresRepository(DATABASE_URL);
  conversationService = new ConversationService(conversationRepo, embedding);
  await conversationService.initialize();
  console.log("Conversation service initialized");
}

const app = buildApp({ service, conversationService });

try {
  await app.listen({ host: HOST, port: PORT });
  console.log(`Backend listening on ${HOST}:${PORT}`);
} catch (err) {
  app.log.error(err);
  process.exit(1);
}
