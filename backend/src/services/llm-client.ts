export interface ChatMessage {
  role: string;
  content: string;
}

export interface ChatCompletionOptions {
  model: string;
  messages: ChatMessage[];
  temperature?: number;
  responseFormat?: { type: string; json_schema?: object };
}

export interface LlmClient {
  chatCompletion(options: ChatCompletionOptions): Promise<string>;
}

export class LiteLlmClient implements LlmClient {
  constructor(
    private baseUrl: string,
    private apiKey?: string,
  ) {}

  async chatCompletion(options: ChatCompletionOptions): Promise<string> {
    const body: Record<string, unknown> = {
      model: options.model,
      messages: options.messages,
      temperature: options.temperature ?? 0.7,
      stream: false,
    };
    if (options.responseFormat) {
      body.response_format = options.responseFormat;
    }

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.apiKey) {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }

    const response = await fetch(`${this.baseUrl}/v1/chat/completions`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(120_000),
    });
    if (!response.ok) {
      throw new Error(`LLM request failed: ${response.status}`);
    }
    const data = (await response.json()) as {
      choices: { message: { content: string } }[];
    };
    return data.choices[0].message.content;
  }
}

export class NoopLlmClient implements LlmClient {
  async chatCompletion(): Promise<string> {
    return "";
  }
}
