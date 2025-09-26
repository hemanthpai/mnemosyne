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
        // Legacy fields - kept for backward compatibility
        original_score?: number;
        query_confidence?: number;
    };
}

export interface LLMSettings {
    // LLM Endpoints
    extraction_endpoint_url: string;
    extraction_model: string;
    extraction_provider_type: 'openai' | 'openai_compatible' | 'ollama';
    extraction_endpoint_api_key: string;
    extraction_timeout: number;
    
    // Embeddings
    embeddings_endpoint_url: string;
    embeddings_model: string;
    embeddings_provider_type: 'openai_compatible' | 'ollama';
    embeddings_endpoint_api_key: string;
    embeddings_timeout: number;
    
    // LLM Parameters
    llm_temperature: number;
    llm_top_p: number;
    llm_top_k: number;
    llm_max_tokens: number;
    
    // Search Configuration (Optimized - simplified from multiple thresholds)
    enable_semantic_connections: boolean;
    semantic_enhancement_threshold: number;
    // Legacy threshold fields - kept for backward compatibility but not used
    search_threshold_direct?: number;
    search_threshold_semantic?: number;
    search_threshold_experiential?: number;
    search_threshold_contextual?: number;
    search_threshold_interest?: number;
    
    // Prompts
    memory_extraction_prompt: string;
    memory_search_prompt: string;
    semantic_connection_prompt: string;
    memory_summarization_prompt: string;
    
    // Metadata
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
    // boosted_threshold removed in backend optimization
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
    memory_summary?: MemorySummary;  // Add this field
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