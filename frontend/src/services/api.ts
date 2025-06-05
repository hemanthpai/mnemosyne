import axios from 'axios';
import {
    ExtractMemoriesResponse,
    LLMSettings,
    Memory,
    RetrieveMemoriesResponse
} from '../types';

const API_BASE_URL = 'http://localhost:8000';

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