import axios from 'axios';
import {
    DeleteAllMemoriesResponse,
    ExtractMemoriesResponse,
    LLMSettings,
    Memory,
    RetrieveMemoriesResponse
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
    userId: string
): Promise<ExtractMemoriesResponse> => {
    try {
        const response = await axios.post<ExtractMemoriesResponse>(`${API_BASE_URL}/api/memories/extract/`, {
            conversation_text: conversationText,
            user_id: userId,
        });
        return response.data;
    } catch (error) {
        console.error('Error extracting memories:', error);
        throw error;
    }
};

export const retrieveMemories = async (
    prompt: string, 
    userId: string
): Promise<RetrieveMemoriesResponse> => {
    try {
        const response = await axios.post<RetrieveMemoriesResponse>(`${API_BASE_URL}/api/memories/retrieve/`, {
            prompt,
            user_id: userId,
        });
        return response.data;
    } catch (error) {
        console.error('Error retrieving memories:', error);
        throw error;
    }
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

// Graph-related endpoints
export const buildMemoryGraph = async (
    userId: string,
    incremental: boolean = true
): Promise<{
    success: boolean;
    message?: string;
    nodes_created?: number;
    relationships_created?: number;
    incremental?: boolean;
    error?: string;
}> => {
    try {
        const response = await axios.post(`${API_BASE_URL}/api/memories/build-graph/`, {
            user_id: userId,
            incremental
        });
        return response.data;
    } catch (error: any) {
        console.error('Error building memory graph:', error);
        return {
            success: false,
            error: error.response?.data?.error || error.message || 'Failed to build memory graph'
        };
    }
};

export const buildMemoryGraphForAllUsers = async (
    incremental: boolean = true
): Promise<{
    success: boolean;
    message?: string;
    nodes_created?: number;
    relationships_created?: number;
    incremental?: boolean;
    total_users?: number;
    failed_users?: string[];
    error?: string;
}> => {
    try {
        const response = await axios.post(`${API_BASE_URL}/api/memories/build-graph/`, {
            build_for_all: true,
            incremental
        });
        return response.data;
    } catch (error: any) {
        console.error('Error building memory graph for all users:', error);
        return {
            success: false,
            error: error.response?.data?.error || error.message || 'Failed to build memory graph for all users'
        };
    }
};

export const checkGraphStatus = async (
    userId: string
): Promise<{
    success: boolean;
    status?: string;
    last_build?: string;
    memory_count?: number;
    is_enabled?: boolean;
    needs_rebuild?: boolean;
    error?: string;
}> => {
    try {
        const response = await axios.get(`${API_BASE_URL}/api/memories/graph-status/`, {
            params: { user_id: userId }
        });
        return response.data;
    } catch (error: any) {
        console.error('Error checking graph status:', error);
        return {
            success: false,
            error: error.response?.data?.error || error.message || 'Failed to check graph status'
        };
    }
};