import type { EmbeddingService } from "./types.js";

export class OllamaEmbeddingService implements EmbeddingService {
  private baseUrl: string;
  private model: string;

  constructor(baseUrl: string, model: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.model = model;
  }

  async embed(text: string): Promise<number[] | null> {
    try {
      const response = await fetch(`${this.baseUrl}/api/embed`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: this.model, input: text }),
        signal: AbortSignal.timeout(30_000),
      });

      if (!response.ok) {
        console.warn(`Ollama embedding request failed: ${response.status}`);
        return null;
      }

      const data = (await response.json()) as { embeddings: number[][] };
      return data.embeddings[0] ?? null;
    } catch (err) {
      console.warn(`Ollama embedding error: ${err}`);
      return null;
    }
  }

  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/api/tags`, {
        signal: AbortSignal.timeout(5_000),
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}
