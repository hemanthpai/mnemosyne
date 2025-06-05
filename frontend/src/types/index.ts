export interface Memory {
    id: string;
    user_id: string;
    content: string;
    metadata: Record<string, any>;
    created_at: string;
    updated_at: string;
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
    memory_extraction_prompt: string;
    memory_categories_list: string[];
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
    message: string;
}

export interface RetrieveMemoriesRequest {
    prompt: string;
    user_id: string;
}

export interface RetrieveMemoriesResponse {
    success: boolean;
    memories: Memory[];
    message: string;
}