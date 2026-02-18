export interface EmbeddingService {
  embed(text: string): Promise<number[] | null>;
  healthCheck(): Promise<boolean>;
}
