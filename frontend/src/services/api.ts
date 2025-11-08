import axios from 'axios';
import {
    StoreConversationTurnResponse,
    SearchConversationsResponse,
    ListConversationsResponse,
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
    threshold: number = 0.5,
    mode: 'fast' | 'deep' = 'fast'  // Phase 3: Search mode
): Promise<SearchConversationsResponse> => {
    const response = await axios.post(`${API_BASE_URL}/api/conversations/search/`, {
        query,
        user_id: userId,
        limit,
        threshold,
        mode,  // Phase 3: Pass search mode to backend
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
// Phase 1: Settings API
// ============================================================================

export const getSettings = async (): Promise<any> => {
    try {
        const response = await axios.get(`${API_BASE_URL}/api/settings/`);
        return response.data;
    } catch (error) {
        console.error('Error fetching settings:', error);
        throw error;
    }
};

export const updateSettings = async (settings: any): Promise<any> => {
    try {
        const response = await axios.put(`${API_BASE_URL}/api/settings/update/`, settings);
        return response.data;
    } catch (error) {
        console.error('Error updating settings:', error);
        throw error;
    }
};

// ============================================================================
// Import API (Phase 0 - will be updated for Phase 1)
// ============================================================================

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

// Alias for importOpenWebUIHistory
export const startOpenWebUIImport = importOpenWebUIHistory;
