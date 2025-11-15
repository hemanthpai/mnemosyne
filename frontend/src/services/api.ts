import axios from 'axios';
import {
    ListConversationsResponse,
    SearchConversationsResponse,
    StoreConversationTurnResponse,
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
// Conversation API
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
    mode: 'fast' | 'deep' = 'fast'
): Promise<SearchConversationsResponse> => {
    const response = await axios.post(`${API_BASE_URL}/api/conversations/search/`, {
        query,
        user_id: userId,
        limit,
        threshold,
        mode,
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
// Settings API
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
// Import API
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

    const response = await axios.post(`${API_BASE_URL}/api/import/start/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
};

export const getImportProgress = async (taskId: string): Promise<ImportProgressResponse> => {
    const response = await axios.get(`${API_BASE_URL}/api/import/progress/`, {
        params: { task_id: taskId }
    });
    return response.data;
};

export const cancelImport = async (taskId: string): Promise<{ success: boolean }> => {
    const response = await axios.post(`${API_BASE_URL}/api/import/cancel/`, {
        task_id: taskId
    });
    return response.data;
};

// Alias for importOpenWebUIHistory
export const startOpenWebUIImport = importOpenWebUIHistory;

// Settings Validation & Model Fetching
export const validateEndpoint = async (
    endpointUrl: string,
    provider: string,
    apiKey?: string
): Promise<{ success: boolean; message?: string; error?: string; provider?: string }> => {
    const response = await axios.post(`${API_BASE_URL}/api/settings/validate-endpoint/`, {
        endpoint_url: endpointUrl,
        provider: provider,
        api_key: apiKey || ''
    });
    return response.data;
};

export const fetchModels = async (
    endpointUrl: string,
    provider: string,
    apiKey?: string
): Promise<{ success: boolean; models?: string[]; count?: number; error?: string }> => {
    const response = await axios.post(`${API_BASE_URL}/api/settings/fetch-models/`, {
        endpoint_url: endpointUrl,
        provider: provider,
        api_key: apiKey || ''
    });
    return response.data;
};

// ============================================================================
// Queue Status API
// ============================================================================

export interface QueueStatusResponse {
    success: boolean;
    timestamp: string;
    queue: {
        waiting_in_queue: number;
        currently_running: number;
        pending: number;  // Legacy field
        processing: number;  // Legacy field
    };
    queue_details: {
        waiting_tasks: Array<{
            name: string;
            func: string;
            lock: number;
        }>;
        waiting_breakdown: Array<{
            func: string;
            count: number;
        }>;
        running_tasks: Array<{
            name: string;
            func: string;
            started: string | null;
            duration_seconds: number;
        }>;
        oldest_waiting_lock: number | null;
    };
    stats: {
        last_hour: {
            total: number;
            successful: number;
            failed: number;
            success_rate: number;
        };
        throughput: {
            tasks_per_minute: number;
            last_5_minutes: number;
        };
    };
    task_breakdown: Array<{
        func: string;
        count: number;
    }>;
    recent_failures: Array<{
        name: string;
        func: string;
        started: string | null;
        stopped: string | null;
        attempt_count: number;
    }>;
    worker_healthy: boolean;
}

export const getQueueStatus = async (): Promise<QueueStatusResponse> => {
    const response = await axios.get(`${API_BASE_URL}/api/queue/status/`);
    return response.data;
};

// ============================================================================
// Benchmark API Functions
// ============================================================================

export const runBenchmark = async (testType: string, dataset: string): Promise<any> => {
    const response = await axios.post(`${API_BASE_URL}/api/benchmarks/run/`, {
        test_type: testType,
        dataset: dataset
    });
    return response.data;
};

export const getBenchmarkStatus = async (taskId: string): Promise<any> => {
    const response = await axios.get(`${API_BASE_URL}/api/benchmarks/status/${taskId}/`);
    return response.data;
};

export const getBenchmarkResults = async (taskId: string): Promise<any> => {
    const response = await axios.get(`${API_BASE_URL}/api/benchmarks/results/${taskId}/`);
    return response.data;
};

export const listDatasets = async (): Promise<any> => {
    const response = await axios.get(`${API_BASE_URL}/api/benchmarks/datasets/`);
    return response.data;
};

export const uploadDataset = async (file: File): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await axios.post(`${API_BASE_URL}/api/benchmarks/datasets/upload/`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

export const cancelBenchmark = async (taskId: string): Promise<any> => {
    const response = await axios.post(`${API_BASE_URL}/api/benchmarks/cancel/`, { task_id: taskId });
    return response.data;
};

// ============================================================================
// Activity Monitor API
// ============================================================================

export interface TaskProgress {
    phase: string;
    current: number;
    total: number;
    percentage: number;
    detail?: string;
    turn_id?: string;
}

export interface RunningTask {
    task_id: string;
    type: string;
    name: string;
    started: string;
    elapsed_seconds: number;
    progress?: TaskProgress;
    turn_id?: string;
}

export interface PendingTask {
    task_id: string;
    type: string;
    name: string;
    queued_at: string;
    wait_seconds: number;
    turn_id?: string;
}

export interface RecentTask {
    task_id: string;
    type: string;
    name: string;
    status: 'completed' | 'failed';
    started: string | null;
    stopped: string | null;
    duration_seconds: number;
}

export interface ActiveTasksResponse {
    success: boolean;
    timestamp: string;
    running: RunningTask[];
    pending: PendingTask[];
    running_count: number;
    pending_count: number;
}

export interface RecentTasksResponse {
    success: boolean;
    tasks: RecentTask[];
}

export const getActiveTasks = async (): Promise<ActiveTasksResponse> => {
    const response = await axios.get(`${API_BASE_URL}/api/tasks/active/`);
    return response.data;
};

export const getRecentTasks = async (): Promise<RecentTasksResponse> => {
    const response = await axios.get(`${API_BASE_URL}/api/tasks/recent/`);
    return response.data;
};

// ============================================================================
// Data Management API
// ============================================================================

export const clearAllData = async (): Promise<{ success: boolean; error?: string }> => {
    const response = await axios.post(`${API_BASE_URL}/api/data/clear-all/`);
    return response.data;
};
