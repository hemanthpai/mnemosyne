import axios from 'axios';
import {
    DeleteAllMemoriesResponse,
    ExtractMemoriesResponse,
    LLMSettings,
    Memory,
    RetrieveMemoriesResponse,
    RetrieveMemoriesRequestOptions
} from '../types/index';

// Auto-detect API base URL based on environment
const getApiBaseUrl = (): string => {
    // Check if we're in a browser environment first
    if (typeof window === 'undefined') {
        return 'http://localhost:8000'; // Fallback for SSR
    }
    
    // Use relative URLs - this will work for both development and production
    // In development: proxied through Vite dev server
    // In production: served by Django on the same host/port
    return '';
};

const API_BASE_URL = getApiBaseUrl();

// Memory extraction and retrieval endpoints
export const extractMemories = async (
    conversationText: string, 
    userId: string,
    options?: { fields?: string[] }
): Promise<ExtractMemoriesResponse> => {
    try {
        const response = await axios.post<ExtractMemoriesResponse>(`${API_BASE_URL}/api/memories/extract/`, {
            conversation_text: conversationText,
            user_id: userId,
            fields: options?.fields || ["id", "content"], // Optimized default - 60-80% smaller responses!
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
            // Optimized defaults for maximum performance
            fields: options?.fields || ["id", "content"], // 60-80% smaller responses!
            include_search_metadata: options?.include_search_metadata || false, // Save bandwidth
            include_summary: options?.include_summary || false, // Save expensive LLM calls
            limit: options?.limit || 99,
            threshold: options?.threshold || 0.7,
            // boosted_threshold removed in backend simplification
        });
        return response.data;
    } catch (error) {
        console.error('Error retrieving memories:', error);
        throw error;
    }
};

// Convenience functions for common use cases
export const retrieveMemoriesWithSummary = async (
    prompt: string, 
    userId: string,
    options?: Omit<RetrieveMemoriesRequestOptions, 'include_summary'>
): Promise<RetrieveMemoriesResponse> => {
    return retrieveMemories(prompt, userId, {
        ...options,
        include_summary: true, // Enable expensive summary for this use case
        fields: options?.fields || ["id", "content", "metadata"], // Include metadata for summary context
    });
};

export const retrieveMemoriesWithSearchDetails = async (
    prompt: string, 
    userId: string,
    options?: Omit<RetrieveMemoriesRequestOptions, 'include_search_metadata'>
): Promise<RetrieveMemoriesResponse> => {
    return retrieveMemories(prompt, userId, {
        ...options,
        include_search_metadata: true, // Include search scoring info
        fields: options?.fields || ["id", "content", "created_at"], // Include timestamps for debugging
    });
};

// Memory CRUD endpoints
export const listAllMemories = async (userId?: string): Promise<Memory[]> => {
    try {
        const url = userId 
            ? `${API_BASE_URL}/api/memories/?user_id=${userId}`
            : `${API_BASE_URL}/api/memories/`;
        
        const response = await axios.get<{
            success: boolean;
            count: number;
            memories: Memory[];
        }>(url);
        
        return response.data.memories;
    } catch (error) {
        console.error('Error listing memories:', error);
        throw error;
    }
};

export const getMemory = async (memoryId: string): Promise<Memory> => {
    try {
        const response = await axios.get<Memory>(`${API_BASE_URL}/api/memories/${memoryId}/`);
        return response.data;
    } catch (error) {
        console.error('Error fetching memory:', error);
        throw error;
    }
};

export const createMemory = async (memoryData: Partial<Memory>): Promise<Memory> => {
    try {
        const response = await axios.post<Memory>(`${API_BASE_URL}/api/memories/`, memoryData);
        return response.data;
    } catch (error) {
        console.error('Error creating memory:', error);
        throw error;
    }
};

export const updateMemory = async (
    memoryId: string, 
    memoryData: Partial<Memory>, 
    partial: boolean = false
): Promise<Memory> => {
    try {
        const method = partial ? 'patch' : 'put';
        const response = await axios[method]<Memory>(`${API_BASE_URL}/api/memories/${memoryId}/`, memoryData);
        return response.data;
    } catch (error) {
        console.error('Error updating memory:', error);
        throw error;
    }
};

export const deleteMemory = async (memoryId: string): Promise<{ success: boolean }> => {
    try {
        await axios.delete(`${API_BASE_URL}/api/memories/${memoryId}/`);
        return { success: true };
    } catch (error) {
        console.error('Error deleting memory:', error);
        throw error;
    }
};

// Add these functions to your existing api.ts file
export const deleteAllMemories = async (userId?: string): Promise<DeleteAllMemoriesResponse> => {
    const payload: any = { confirm: true };
    if (userId) {
        payload.user_id = userId;
    }
    
    const response = await fetch(`${API_BASE_URL}/api/memories/delete-all/`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to delete memories');
    }

    return response.json();
};

export const clearVectorDatabase = async (): Promise<DeleteAllMemoriesResponse> => {
    return deleteAllMemories(); // Same endpoint, no user_id = clear all
};

// Settings endpoints
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

export const getPromptTokenCounts = async (): Promise<{
    success: boolean;
    token_counts?: {
        memory_extraction_prompt: number;
        memory_search_prompt: number;
        semantic_connection_prompt: number;
        memory_summarization_prompt: number;
    };
    model_name?: string;
    error?: string;
}> => {
    const response = await fetch(`${API_BASE_URL}/api/settings/prompt-token-counts/`);
    
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
};

// Backend proxy endpoint validation and model fetching
export const validateEndpoint = async (
    url: string,
    provider_type: string,
    api_key?: string
): Promise<{
    success: boolean;
    error?: string;
}> => {
    try {
        const response = await axios.post(`${API_BASE_URL}/api/settings/validate-endpoint/`, {
            url,
            provider_type,
            api_key
        });
        return response.data;
    } catch (error: any) {
        console.error('Error validating endpoint:', error);
        return {
            success: false,
            error: error.response?.data?.error || error.message || 'Failed to validate endpoint'
        };
    }
};

export const fetchModels = async (
    url: string,
    provider_type: string,
    api_key?: string
): Promise<{
    success: boolean;
    models?: string[];
    error?: string;
}> => {
    try {
        const response = await axios.post(`${API_BASE_URL}/api/settings/fetch-models/`, {
            url,
            provider_type,
            api_key
        });
        return response.data;
    } catch (error: any) {
        console.error('Error fetching models:', error);
        return {
            success: false,
            error: error.response?.data?.error || error.message || 'Failed to fetch models'
        };
    }
};