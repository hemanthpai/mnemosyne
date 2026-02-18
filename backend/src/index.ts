import { buildApp } from "./app.js";

const HOST = process.env.HOST ?? "0.0.0.0";
const PORT = parseInt(process.env.PORT ?? "3000", 10);

const app = buildApp();

try {
  await app.listen({ host: HOST, port: PORT });
  console.log(`Backend listening on ${HOST}:${PORT}`);
} catch (err) {
  app.log.error(err);
  process.exit(1);
}
