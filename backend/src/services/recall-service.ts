import type { ConversationService } from "./conversation-service.js";
import type { LlmClient } from "./llm-client.js";
import type { Conversation } from "../types/conversation.js";
import {
  selectDiverse,
  type RecallCandidate,
} from "./recall-diversity.js";

const DEFAULT_QUERY_MODEL = "nousresearch/hermes-4-70b";
const DEFAULT_EXTRACT_MODEL = "openai/Hermes-4.3-36b";
const EXTRACTION_CONCURRENCY = 2;

export interface RecallOptions {
  queryModel?: string;
  extractModel?: string;
}

export interface RecallResult {
  context: string;
  conversations: { id: string; title: string; score: number }[];
  totalFound: number;
}

export class RecallService {
  private queryModel: string;
  private extractModel: string;

  constructor(
    private conversationService: ConversationService,
    private llm: LlmClient,
    options?: RecallOptions,
  ) {
    this.queryModel = options?.queryModel || DEFAULT_QUERY_MODEL;
    this.extractModel = options?.extractModel || DEFAULT_EXTRACT_MODEL;
  }

  async recall(query: string, userId?: string): Promise<RecallResult> {
    // Step 1: Generate search queries via LLM
    const queries = await this.generateQueries(query);

    // Step 2: Multi-query search in parallel
    const searchResults = await Promise.all(
      queries.map((q) =>
        this.conversationService.search(
          q,
          undefined,
          10,
          ["avg_embedding", "centroids"],
          userId,
        ),
      ),
    );

    // Flatten results into candidates
    const allCandidates: RecallCandidate[] = searchResults
      .flat()
      .map((conv) => ({
        id: conv.id,
        title: conv.title || "Untitled",
        score: conv.score ?? 0,
        tags: conv.tags || [],
        avgEmbedding: conv.avgEmbedding || null,
        centroids: conv.centroids || null,
      }));

    if (allCandidates.length === 0) {
      return { context: "", conversations: [], totalFound: 0 };
    }

    // Step 3: Dedup + k-means + MMR selection
    const selected = selectDiverse(allCandidates);
    const totalFound = new Set(allCandidates.map((c) => c.id)).size;

    // Step 4: Fetch full conversations in parallel
    const fullConversations = await Promise.all(
      selected.map((s) => this.conversationService.getById(s.id)),
    );
    const validConversations = fullConversations.filter(
      (c): c is Conversation => c !== null,
    );

    if (validConversations.length === 0) {
      return { context: "", conversations: [], totalFound };
    }

    // Step 5: Per-conversation LLM extraction (limited concurrency)
    const extractions = await this.extractAll(query, validConversations);

    // Step 6: Aggregate into markdown
    const context = this.buildContext(extractions);

    return {
      context,
      conversations: selected.map((s) => ({
        id: s.id,
        title: s.title,
        score: s.score,
      })),
      totalFound,
    };
  }

  private async generateQueries(userMessage: string): Promise<string[]> {
    try {
      const content = await this.llm.chatCompletion({
        model: this.queryModel,
        messages: [
          {
            role: "system",
            content:
              "Your job is to generate 2-3 diverse search queries to find relevant past conversations to help another AI Assistant agent respond to the user message specified. Each query should target a different aspect: key topics, entities, or related concepts. Specifically, you should seek to find out what has the user shared or asked about the relevant topics, entities, or related concepts. Return a JSON object with a \"queries\" array of strings.",
          },
          { role: "user", content: userMessage },
        ],
        temperature: 0.7,
        responseFormat: {
          type: "json_schema",
          json_schema: {
            name: "search_queries",
            strict: true,
            schema: {
              type: "object",
              properties: {
                queries: { type: "array", items: { type: "string" } },
              },
              required: ["queries"],
              additionalProperties: false,
            },
          },
        },
      });

      const parsed = JSON.parse(content);
      if (Array.isArray(parsed.queries) && parsed.queries.length > 0) {
        return parsed.queries;
      }
      return [userMessage];
    } catch {
      return [userMessage];
    }
  }

  private async extractAll(
    userMessage: string,
    conversations: Conversation[],
  ): Promise<{ title: string; content: string }[]> {
    const results: { title: string; content: string }[] = [];

    // Process with limited concurrency
    for (let i = 0; i < conversations.length; i += EXTRACTION_CONCURRENCY) {
      const batch = conversations.slice(i, i + EXTRACTION_CONCURRENCY);
      const batchResults = await Promise.all(
        batch.map((conv) => this.extractFromConversation(userMessage, conv)),
      );
      for (const r of batchResults) {
        if (r) results.push(r);
      }
    }

    return results;
  }

  private async extractFromConversation(
    userMessage: string,
    conv: Conversation,
  ): Promise<{ title: string; content: string } | null> {
    const title = conv.title || "Untitled";
    const messages = (conv.messages || [])
      .map((m) => `${m.role}: ${m.content}`)
      .join("\n");

    try {
      const extraction = await this.llm.chatCompletion({
        model: this.extractModel,
        messages: [
          {
            role: "system",
            content:
              "You are provided with a past conversation between the user and an AI Assistant. You are also provided with a user query the AI Assistant is tasked with responding to. Your job is to analyze the provided historical conversation and extract any, all, and only information that the AI Assistant will find highly relevant or helpful to answer the user's query. Be concise and specific. If nothing is relevant, respond with exactly NONE. It is VERY IMPORTANT that you thoroughly review your work and ensure you are ONLY extracting information the AI Assistant will find helpful and relevant to the users query. Think out loud why and how the extracted content will help answer the user's query. Don't include your thinking in the final output.",
          },
          {
            role: "user",
            content: `User query: ${userMessage}\n\nPast conversation "${title}":\n${messages}`,
          },
        ],
        temperature: 0.3,
      });

      if (
        !extraction ||
        extraction.trim().toUpperCase() === "NONE"
      ) {
        return null;
      }

      return { title, content: extraction.trim() };
    } catch {
      return null;
    }
  }

  private buildContext(
    extractions: { title: string; content: string }[],
  ): string {
    if (extractions.length === 0) return "";

    const sections = extractions.map(
      (e) => `### From: ${e.title}\n${e.content}`,
    );
    return `## Relevant Context from Past Conversations\n\n${sections.join("\n\n")}`;
  }
}
