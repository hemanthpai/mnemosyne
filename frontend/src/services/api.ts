import axios from 'axios';
import {
    StoreConversationTurnResponse,
    SearchConversationsResponse,
    ListConversationsResponse,
    // Legacy types
    DeleteAllMemoriesResponse,
    ExtractMemoriesResponse,
    LLMSettings,
    Memory,
    RetrieveMemoriesResponse,
    RetrieveMemoriesRequestOptions
} from '../types/index';

// Auto-detect API base URL based on environment
const getApiBaseUrl = (): string => {
    if (typeof window === 'undefined') {
        return 'http://localhost:8000';
    }
    return '';
};

const API_BASE_URL = getApiBaseUrl();

// ============================================================================
// Phase 1: Simple Conversation API (New)
// ============================================================================

export const storeConversationTurn = async (
    userId: string,
    sessionId: string,
    userMessage: string,
    assistantMessage: string
): Promise<StoreConversationTurnResponse> => {
    const response = await axios.post(`${API_BASE_URL}/api/conversations/store/`, {
        user_id: userId,
        session_id: sessionId,
        user_message: userMessage,
        assistant_message: assistantMessage,
    });
    return response.data;
};

export const searchConversations = async (
    query: string,
    userId: string,
    limit: number = 10,
    threshold: number = 0.5
): Promise<SearchConversationsResponse> => {
    const response = await axios.post(`${API_BASE_URL}/api/conversations/search/`, {
        query,
        user_id: userId,
        limit,
        threshold,
    });
    return response.data;
};

export const listConversations = async (
    userId: string,
    limit: number = 50
): Promise<ListConversationsResponse> => {
    const response = await axios.get(`${API_BASE_URL}/api/conversations/list/`, {
        params: { user_id: userId, limit }
    });
    return response.data;
};

// ============================================================================
// Legacy API (Phase 0 - kept for compatibility during transition)
// ============================================================================

export const extractMemories = async (
    conversationText: string,
    userId: string,
    options?: { fields?: string[] }
): Promise<ExtractMemoriesResponse> => {
    try {
        const response = await axios.post<ExtractMemoriesResponse>(`${API_BASE_URL}/api/memories/extract/`, {
            conversation_text: conversationText,
            user_id: userId,
            fields: options?.fields || ["id", "content"],
        });
        return response.data;
    } catch (error) {
        console.error('Error extracting memories:', error);
        throw error;
    }
};

export const retrieveMemories = async (
    prompt: string,
    userId: string,
    options?: RetrieveMemoriesRequestOptions
): Promise<RetrieveMemoriesResponse> => {
    try {
        const response = await axios.post<RetrieveMemoriesResponse>(`${API_BASE_URL}/api/memories/retrieve/`, {
            prompt,
            user_id: userId,
            fields: options?.fields || ["id", "content"],
            include_search_metadata: options?.include_search_metadata || false,
            include_summary: options?.include_summary || false,
            limit: options?.limit || 99,
            threshold: options?.threshold || 0.7,
        });
        return response.data;
    } catch (error) {
        console.error('Error retrieving memories:', error);
        throw error;
    }
};

export const retrieveMemoriesWithSummary = async (
    prompt: string,
    userId: string,
    options?: Omit<RetrieveMemoriesRequestOptions, 'include_summary'>
): Promise<RetrieveMemoriesResponse> => {
    return retrieveMemories(prompt, userId, {
        ...options,
        include_summary: true,
        fields: options?.fields || ["id", "content", "metadata"],
    });
};

export const retrieveMemoriesWithSearchDetails = async (
    prompt: string,
    userId: string,
    options?: Omit<RetrieveMemoriesRequestOptions, 'include_search_metadata'>
): Promise<RetrieveMemoriesResponse> => {
    return retrieveMemories(prompt, userId, {
        ...options,
        include_search_metadata: true,
        fields: options?.fields || ["id", "content", "created_at"],
    });
};

export const listAllMemories = async (userId?: string): Promise<Memory[]> => {
    try {
        const url = userId
            ? `${API_BASE_URL}/api/memories/?user_id=${userId}`
            : `${API_BASE_URL}/api/memories/`;

        const response = await axios.get(url);
        return response.data.memories || [];
    } catch (error) {
        console.error('Error listing memories:', error);
        throw error;
    }
};

export const deleteAllMemories = async (userId?: string): Promise<DeleteAllMemoriesResponse> => {
    try {
        const url = `${API_BASE_URL}/api/memories/delete-all/`;
        const response = await axios.delete<DeleteAllMemoriesResponse>(url, {
            params: userId ? { user_id: userId } : {},
        });
        return response.data;
    } catch (error) {
        console.error('Error deleting memories:', error);
        throw error;
    }
};

export const getSettings = async (): Promise<LLMSettings> => {
    try {
        const response = await axios.get<LLMSettings>(`${API_BASE_URL}/api/settings/`);
        return response.data;
    } catch (error) {
        console.error('Error fetching settings:', error);
        throw error;
    }
};

export const updateSettings = async (settings: Partial<LLMSettings>): Promise<LLMSettings> => {
    try {
        const response = await axios.put<LLMSettings>(`${API_BASE_URL}/api/settings/`, settings);
        return response.data;
    } catch (error) {
        console.error('Error updating settings:', error);
        throw error;
    }
};

export const testConnection = async (): Promise<{ success: boolean; error?: string }> => {
    try {
        const response = await axios.get(`${API_BASE_URL}/api/memories/test-connection/`);
        return response.data;
    } catch (error) {
        console.error('Error testing connection:', error);
        throw error;
    }
};

export interface MemoryStatsResponse {
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

export const getMemoryStats = async (userId?: string): Promise<MemoryStatsResponse> => {
    try {
        const url = userId
            ? `${API_BASE_URL}/api/memories/stats/?user_id=${userId}`
            : `${API_BASE_URL}/api/memories/stats/`;
        const response = await axios.get<MemoryStatsResponse>(url);
        return response.data;
    } catch (error) {
        console.error('Error fetching memory stats:', error);
        throw error;
    }
};

export interface ImportProgressResponse {
    status: string;
    progress: number;
    current_chat?: number;
    total_chats?: number;
    memories_extracted?: number;
    errors_encountered?: number;
    error?: string;
}

export const importOpenWebUIHistory = async (
    file: File,
    userId: string,
    dryRun: boolean = false
): Promise<{ success: boolean; task_id: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', userId);
    formData.append('dry_run', dryRun.toString());

    const response = await axios.post(`${API_BASE_URL}/api/memories/import/start/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
};

export const getImportProgress = async (taskId: string): Promise<ImportProgressResponse> => {
    const response = await axios.get(`${API_BASE_URL}/api/memories/import/progress/`, {
        params: { task_id: taskId }
    });
    return response.data;
};

export const cancelImport = async (taskId: string): Promise<{ success: boolean }> => {
    const response = await axios.post(`${API_BASE_URL}/api/memories/import/cancel/`, {
        task_id: taskId
    });
    return response.data;
};

// ============================================================================
// Deprecated/Stub Functions (for backward compatibility with old pages)
// ============================================================================

// Alias for importOpenWebUIHistory
export const startOpenWebUIImport = importOpenWebUIHistory;

// Memory CRUD stubs (not implemented in Phase 1)
export const getMemory = async (_id: string): Promise<Memory> => {
    throw new Error('getMemory not implemented in Phase 1 - Please use DevTools page to test conversation storage and search');
};

export const updateMemory = async (_id: string, _data: Partial<Memory>, _updateVector?: boolean): Promise<Memory> => {
    throw new Error('updateMemory not implemented in Phase 1 - Memory editing will be added in Phase 3');
};

export const deleteMemory = async (_id: string): Promise<{ success: boolean }> => {
    throw new Error('deleteMemory not implemented in Phase 1 - Memory deletion will be added in Phase 3');
};

// Settings helper stubs (not needed in Phase 1)
export const fetchModels = async (_endpoint: string, _provider: string, _apiKey?: string): Promise<{ success: boolean; models?: string[]; error?: string }> => {
    console.warn('fetchModels not implemented in Phase 1 - Settings are configured via environment variables');
    return { success: false, models: [], error: 'Not implemented in Phase 1' };
};

export const validateEndpoint = async (_endpoint: string, _provider: string, _apiKey?: string): Promise<{ success: boolean; valid?: boolean; error?: string }> => {
    console.warn('validateEndpoint not implemented in Phase 1 - Settings are configured via environment variables');
    return { success: false, valid: false, error: 'Not implemented in Phase 1' };
};

export const getPromptTokenCounts = async (): Promise<{ success: boolean; token_counts?: any }> => {
    console.warn('getPromptTokenCounts not implemented in Phase 1 - Prompts are simplified');
    return { success: false };
};
