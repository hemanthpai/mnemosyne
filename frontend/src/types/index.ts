// ============================================================================
// Phase 1: ConversationTurn Types (New Simplified Architecture)
// ============================================================================

export interface ConversationTurn {
    id: string;
    user_id: string;
    session_id: string;
    turn_number: number;
    user_message: string;
    assistant_message: string;
    timestamp: string;
    vector_id: string;
    extracted: boolean;
}

export interface StoreConversationTurnResponse {
    success: boolean;
    turn_id: string;
    turn_number: number;
    latency_ms: number;
    error?: string;
}

export interface SearchConversationsResponse {
    success: boolean;
    count: number;
    results: Array<{
        id: string;
        user_message: string;
        assistant_message: string;
        timestamp: string;
        score: number;
        session_id: string;
        turn_number: number;
    }>;
    latency_ms: number;
    error?: string;
}

export interface ListConversationsResponse {
    success: boolean;
    count: number;
    conversations: ConversationTurn[];
    latency_ms: number;
    error?: string;
}

// ============================================================================
// Phase 1: Simplified Settings (Embeddings Only)
// ============================================================================

export interface SimplifiedSettings {
    // Embeddings Configuration
    embeddings_endpoint_url: string;
    embeddings_model: string;
    embeddings_provider: 'openai' | 'openai_compatible' | 'ollama';
    embeddings_api_key?: string;
    embeddings_timeout: number;
}

// ============================================================================
// Legacy Types (Phase 0 - kept for compatibility, will be removed in Phase 3)
// ============================================================================

export interface Memory {
    id: string;
    user_id: string;
    content: string;
    metadata: {
        tags: string[];
        confidence: number;
        context?: string;
        connections?: string[];
        extraction_source?: string;
        model_used?: string;
        created_at?: string;
        [key: string]: any;
    };
    created_at: string;
    updated_at: string;
    search_metadata?: {
        search_score: number;
        search_type?: string;
        search_time_ms?: number;
        original_score?: number;
        query_confidence?: number;
    };
}

export interface LLMSettings {
    extraction_endpoint_url: string;
    extraction_model: string;
    extraction_provider_type: 'openai' | 'openai_compatible' | 'ollama';
    extraction_endpoint_api_key: string;
    extraction_timeout: number;

    embeddings_endpoint_url: string;
    embeddings_model: string;
    embeddings_provider_type: 'openai_compatible' | 'ollama';
    embeddings_endpoint_api_key: string;
    embeddings_timeout: number;

    llm_temperature: number;
    llm_top_p: number;
    llm_top_k: number;
    llm_max_tokens: number;

    enable_semantic_connections: boolean;
    semantic_enhancement_threshold: number;
    search_threshold_direct?: number;
    search_threshold_semantic?: number;
    search_threshold_experiential?: number;
    search_threshold_contextual?: number;
    search_threshold_interest?: number;

    memory_extraction_prompt: string;
    memory_search_prompt: string;
    semantic_connection_prompt: string;
    memory_summarization_prompt: string;

    created_at: string;
    updated_at: string;
}

export interface ApiResponse<T> {
    success: boolean;
    data?: T;
    error?: string;
}

export interface ExtractMemoriesRequest {
    conversation_text: string;
    user_id: string;
    fields?: string[];
}

export interface RetrieveMemoriesRequestOptions {
    fields?: string[];
    include_search_metadata?: boolean;
    include_summary?: boolean;
    limit?: number;
    threshold?: number;
}

export interface ExtractMemoriesResponse {
    success: boolean;
    memories_extracted: number;
    memories: Memory[];
}

export interface RetrieveMemoriesRequest {
    prompt: string;
    user_id: string;
}

export interface MemorySummary {
    summary: string;
}

export interface RetrieveMemoriesResponse {
    success: boolean;
    memories: Memory[];
    memory_summary?: MemorySummary;
    count: number;
    search_queries_generated: number;
    model_used: string;
    query_params: {
        limit: number;
        threshold: number;
    };
}

export interface DeleteAllMemoriesResponse {
    success: boolean;
    message?: string;
    error?: string;
    deleted_count: number;
    user_id?: string;
}

export interface MemoryStatsData {
    success: boolean;
    total_memories: number;
    domain_distribution: Record<string, number>;
    top_tags: Record<string, number>;
    vector_collection_info?: {
        points_count: number;
        vector_count?: number;
        status?: string;
        config?: Record<string, any>;
    };
}
