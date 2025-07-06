import { Memory } from './types/index';

export interface MemorySummary {
    summary: string;
    key_points: string[];
    relevant_context: string;
    confidence: number;
    memory_usage: {
        total_memories: number;
        highly_relevant: number;
        moderately_relevant: number;
        context_relevant: number;
    };
}

export interface RetrieveMemoriesResponse {
    success: boolean;
    memories: Memory[];
    memory_summary?: MemorySummary;  // Add this field
    count: number;
    search_queries_generated: number;
    model_used: string;
    query_params: {
        limit: number;
        threshold: number;
    };
}