import type { EmbeddingService } from "./types.js";

export class NoopEmbeddingService implements EmbeddingService {
  async embed(): Promise<null> {
    return null;
  }

  async healthCheck(): Promise<boolean> {
    return true;
  }
}
