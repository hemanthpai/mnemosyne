// ============================================================================
// ConversationTurn Types
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
    results: Array<SearchResult>;
    latency_ms: number;
    mode?: 'fast' | 'deep';
    error?: string;
}

// Unified search result type (supports both conversations and atomic notes)
export interface SearchResult {
    id: string;
    user_message?: string;  // For conversation results
    assistant_message?: string;  // For conversation results
    content?: string;  // For atomic note results
    timestamp?: string;
    score?: number;
    session_id?: string;
    turn_number?: number;

    // Atomic note fields
    note_type?: string;
    context?: string;
    confidence?: number;
    importance_score?: number;
    tags?: string[];
    created_at?: string;

    // Multi-tier search metadata
    source?: 'working_memory' | 'raw_conversation' | 'atomic_note' | 'graph_traversal';
    combined_score?: number;

    // Graph traversal metadata
    depth?: number;
    relationship_type?: string;
    relationship_strength?: number;
}

export interface ListConversationsResponse {
    success: boolean;
    count: number;
    conversations: ConversationTurn[];
    latency_ms: number;
    error?: string;
}

// ============================================================================
// Atomic Notes and Knowledge Graph Types
// ============================================================================

export interface AtomicNote {
    id: string;
    user_id: string;
    content: string;
    note_type: string;
    context: string;
    confidence: number;
    importance_score: number;
    vector_id: string;
    tags: string[];
    created_at: string;
    updated_at: string;
    source_turn_id?: string;
}

export interface NoteRelationship {
    id: string;
    from_note_id: string;
    to_note_id: string;
    relationship_type: 'related_to' | 'contradicts' | 'refines' | 'context_for' | 'follows_from';
    strength: number;
    created_at: string;
}

// ============================================================================
// Settings Types
// ============================================================================

export interface SimplifiedSettings {
    // Embeddings Configuration
    embeddings_endpoint_url: string;
    embeddings_model: string;
    embeddings_provider: 'openai' | 'openai_compatible' | 'ollama';
    embeddings_api_key?: string;
    embeddings_timeout: number;
}

