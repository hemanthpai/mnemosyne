export interface Memory {
    id: string;
    user_id: string;
    content: string;
    metadata: {
        tags: string[];
        confidence: number;
        entity_type: 'person' | 'place' | 'preference' | 'skill' | 'fact' | 'event' | 'general';
        inference_level: 'stated' | 'inferred' | 'implied';
        certainty: number;
        evidence: string;
        relationship_hints?: ('supports' | 'contradicts' | 'relates_to' | 'temporal_sequence' | 'updates')[];
        extraction_source?: string;
        model_used?: string;
        created_at?: string;
        [key: string]: any;
    };
    fact_type: 'mutable' | 'immutable' | 'temporal';
    created_at: string;
    updated_at: string;
    // New hybrid architecture fields
    conversation_chunk_ids: string[];
    hybrid_search_score?: number;
    ranking_details?: {
        base_score: number;
        conversation_boost: number;
        temporal_boost: number;
        inference_penalty: number;
        entity_boost: number;
        relationship_boost: number;
        confidence_factor: number;
        final_score: number;
    };
}

export interface ConversationChunk {
    id: string;
    user_id: string;
    content: string;
    vector_id: string;
    timestamp: string;
    metadata: {
        chunk_index?: number;
        total_chunks?: number;
        source?: string;
        [key: string]: any;
    };
    extracted_memory_ids: string[];
    created_at: string;
    updated_at: string;
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
    
    // Search Configuration
    enable_semantic_connections: boolean;
    semantic_enhancement_threshold: number;
    search_threshold_direct: number;
    search_threshold_semantic: number;
    search_threshold_experiential: number;
    search_threshold_contextual: number;
    search_threshold_interest: number;
    
    // Memory Consolidation
    enable_memory_consolidation: boolean;
    consolidation_similarity_threshold: number;
    consolidation_auto_threshold: number;
    consolidation_strategy: 'automatic' | 'llm_guided' | 'manual';
    consolidation_max_group_size: number;
    consolidation_batch_size: number;

    // Graph-Enhanced Retrieval
    enable_graph_enhanced_retrieval: boolean;
    graph_build_status: 'not_built' | 'building' | 'built' | 'failed' | 'outdated' | 'partial';
    graph_last_build: string | null;
    
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
}

export interface ExtractMemoriesResponse {
    success: boolean;
    memories_extracted: number;
    conflicts_resolved: number;
    duplicates_consolidated: number;
    memories: Memory[];
    model_used: string;
    // New hybrid architecture information
    hybrid_storage: {
        conversation_chunks_created: number;
        chunk_ids: string[];
        conversation_length: number;
        chunks_generated: number;
    };
    graph_build_result?: {
        success: boolean;
        relationships_created: number;
        incremental: boolean;
    };
}

export interface RetrieveMemoriesRequest {
    prompt: string;
    user_id: string;
}

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
    memory_summary?: MemorySummary;
    count: number;
    search_queries_generated: number;
    model_used: string;
    query_params: {
        limit: number;
        threshold: number;
    };
    // New hybrid architecture information
    hybrid_search_info: {
        graph_enabled: boolean;
        conversation_context_available: boolean;
    };
    conversation_context?: {
        total_sessions: number;
        total_expanded_chunks: number;
        context_summary: {
            total_content_length: number;
            time_span_hours?: number;
            earliest_timestamp?: string;
            latest_timestamp?: string;
            memories_referenced: number;
            avg_chunk_length: number;
        };
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

// New conversation management types
export interface ConversationChunkResponse {
    success: boolean;
    chunks: ConversationChunk[];
    count?: number;
}

export interface ConversationChunkMemoriesResponse {
    success: boolean;
    memories: Memory[];
    count: number;
    chunk_info: {
        id: string;
        content_preview: string;
        timestamp: string;
        total_content_length?: number;
    };
}

export interface ConversationSearchRequest {
    query: string;
    user_id: string;
    limit?: number;
    threshold?: number;
}

export interface ConversationSearchResponse {
    success: boolean;
    results: {
        chunk_id: string;
        content: string;
        score: number;
        timestamp?: string;
        extracted_memories_count: number;
        content_preview: string;
    }[];
    count: number;
    query: string;
    search_params: {
        limit: number;
        threshold: number;
    };
}