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

