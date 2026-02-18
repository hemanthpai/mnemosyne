import { buildApp } from "./app.js";
import { InMemoryRepository, PostgresRepository } from "./repository/index.js";
import type { MemoryRepository } from "./repository/index.js";

const HOST = process.env.HOST ?? "0.0.0.0";
const PORT = parseInt(process.env.PORT ?? "3000", 10);
const DATABASE_URL = process.env.DATABASE_URL;

let repository: MemoryRepository;

if (DATABASE_URL) {
  console.log("Using PostgreSQL repository");
  repository = new PostgresRepository(DATABASE_URL);
} else {
  console.warn("DATABASE_URL not set — using in-memory repository (data will be lost on restart)");
  repository = new InMemoryRepository();
}

await repository.initialize();

const app = buildApp({ repository });

try {
  await app.listen({ host: HOST, port: PORT });
  console.log(`Backend listening on ${HOST}:${PORT}`);
} catch (err) {
  app.log.error(err);
  process.exit(1);
}
