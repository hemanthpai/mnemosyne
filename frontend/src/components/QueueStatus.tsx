import React, { useEffect, useState } from "react";
import axios from "axios";

interface QueueHealth {
    success: boolean;
    health_status: 'healthy' | 'degraded' | 'unhealthy';
    action_required: boolean;
    issues: Array<{
        type: string;
        severity: 'success' | 'info' | 'warning' | 'error';
        message: string;
        action: string | null;
        action_label: string | null;
    }>;
    metrics: {
        queue_size: number;
        stuck_tasks: number;
        recent_completions: number;
        recent_failures: number;
    };
}

const QueueStatus: React.FC = () => {
    const [healthData, setHealthData] = useState<QueueHealth | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [actionLoading, setActionLoading] = useState<boolean>(false);
    const [actionMessage, setActionMessage] = useState<string | null>(null);
    const [isExpanded, setIsExpanded] = useState<boolean>(true);

    const fetchHealthData = async () => {
        try {
            const response = await axios.get('/api/queue/health/');
            setHealthData(response.data);
            setError(null);
        } catch (err) {
            console.error('Error fetching queue health:', err);
            setError('Failed to load queue status');
        } finally {
            setLoading(false);
        }
    };

    const handleClearStuckTasks = async () => {
        if (!window.confirm('Are you sure you want to clear stuck tasks? This will remove tasks that haven\'t been processed in >30 minutes.')) {
            return;
        }

        setActionLoading(true);
        setActionMessage(null);

        try {
            const response = await axios.post('/api/queue/clear-stuck/');
            if (response.data.success) {
                setActionMessage(`✓ ${response.data.message}`);
                // Refresh health data after clearing
                await fetchHealthData();
                // Clear success message after 5 seconds
                setTimeout(() => setActionMessage(null), 5000);
            }
        } catch (err: any) {
            setActionMessage(`✗ Failed: ${err.response?.data?.error || err.message}`);
        } finally {
            setActionLoading(false);
        }
    };

    useEffect(() => {
        // Fetch immediately
        fetchHealthData();

        // Poll every 5 seconds (slower than before since we have Activity Monitor)
        const interval = setInterval(fetchHealthData, 5000);

        return () => clearInterval(interval);
    }, []);

    if (loading && !healthData) {
        return (
            <div className="bg-gray-50 dark:bg-gray-800 rounded-lg shadow p-6">
                <div className="animate-pulse">
                    <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-4"></div>
                    <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
                </div>
            </div>
        );
    }

    if (error && !healthData) {
        return (
            <div className="bg-gray-50 dark:bg-gray-800 rounded-lg shadow p-6">
                <div className="text-red-500 dark:text-red-400">{error}</div>
            </div>
        );
    }

    if (!healthData) {
        return null;
    }

    const { health_status, action_required, issues, metrics } = healthData;

    const getStatusColor = () => {
        switch (health_status) {
            case 'healthy':
                return 'bg-green-500';
            case 'degraded':
                return 'bg-yellow-500';
            case 'unhealthy':
                return 'bg-red-500';
            default:
                return 'bg-gray-500';
        }
    };

    const getStatusTextColor = () => {
        switch (health_status) {
            case 'healthy':
                return 'text-green-600 dark:text-green-400';
            case 'degraded':
                return 'text-yellow-600 dark:text-yellow-400';
            case 'unhealthy':
                return 'text-red-600 dark:text-red-400';
            default:
                return 'text-gray-600 dark:text-gray-400';
        }
    };

    const getSeverityStyles = (severity: string) => {
        switch (severity) {
            case 'success':
                return 'bg-green-50 dark:bg-green-900 border-green-200 dark:border-green-700 text-green-800 dark:text-green-100';
            case 'info':
                return 'bg-blue-50 dark:bg-blue-900 border-blue-200 dark:border-blue-700 text-blue-800 dark:text-blue-100';
            case 'warning':
                return 'bg-yellow-50 dark:bg-yellow-900 border-yellow-200 dark:border-yellow-700 text-yellow-800 dark:text-yellow-100';
            case 'error':
                return 'bg-red-50 dark:bg-red-900 border-red-200 dark:border-red-700 text-red-800 dark:text-red-100';
            default:
                return 'bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-700 text-gray-800 dark:text-gray-100';
        }
    };

    return (
        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg shadow">
            {/* Header - Clickable to toggle */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full px-6 py-4 border-b border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                            Task Queue Status
                        </h3>
                        <div className="flex items-center gap-2">
                            <div className={`w-2 h-2 rounded-full ${getStatusColor()}`}></div>
                            <span className={`text-xs font-medium ${getStatusTextColor()}`}>
                                {health_status.charAt(0).toUpperCase() + health_status.slice(1)}
                            </span>
                        </div>
                    </div>
                    <svg
                        className={`w-5 h-5 text-gray-500 dark:text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                </div>
            </button>

            {/* Metrics Grid - Collapsible */}
            {isExpanded && (
            <div className="px-6 py-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
                    {/* Queue Size */}
                    <div className="flex flex-col">
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                            Queue Size
                        </span>
                        <span className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                            {metrics.queue_size}
                        </span>
                    </div>

                    {/* Stuck Tasks */}
                    <div className="flex flex-col">
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                            Stuck Tasks
                        </span>
                        <span className={`text-2xl font-bold ${metrics.stuck_tasks > 0 ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-gray-100'}`}>
                            {metrics.stuck_tasks}
                        </span>
                    </div>

                    {/* Recent Completions */}
                    <div className="flex flex-col">
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                            Last 5 Min
                        </span>
                        <span className="text-2xl font-bold text-green-600 dark:text-green-400">
                            {metrics.recent_completions}
                        </span>
                    </div>

                    {/* Recent Failures */}
                    <div className="flex flex-col">
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                            Failures (1h)
                        </span>
                        <span className={`text-2xl font-bold ${metrics.recent_failures > 0 ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-gray-100'}`}>
                            {metrics.recent_failures}
                        </span>
                    </div>
                </div>

                {/* Issues/Status Messages */}
                <div className="space-y-2">
                    {issues.map((issue, index) => (
                        <div
                            key={index}
                            className={`rounded-lg p-3 border ${getSeverityStyles(issue.severity)}`}
                        >
                            <div className="flex items-start justify-between">
                                <div className="flex-1">
                                    <p className="text-sm font-medium">{issue.message}</p>
                                </div>
                                {issue.action === 'clear_stuck_tasks' && (
                                    <button
                                        onClick={handleClearStuckTasks}
                                        disabled={actionLoading}
                                        className="ml-3 px-3 py-1 bg-yellow-600 text-white text-xs font-medium rounded hover:bg-yellow-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {actionLoading ? 'Clearing...' : issue.action_label}
                                    </button>
                                )}
                            </div>
                        </div>
                    ))}

                    {/* Action Message */}
                    {actionMessage && (
                        <div className={`rounded-lg p-3 border ${actionMessage.startsWith('✓') ? 'bg-green-50 dark:bg-green-900 border-green-200 dark:border-green-700 text-green-800 dark:text-green-100' : 'bg-red-50 dark:bg-red-900 border-red-200 dark:border-red-700 text-red-800 dark:text-red-100'}`}>
                            <p className="text-sm font-medium">{actionMessage}</p>
                        </div>
                    )}
                </div>

                {/* Help Text */}
                {action_required && (
                    <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                            <strong>Tip:</strong> Use the Activity Monitor page to see real-time task progress and detailed information about running tasks.
                        </p>
                    </div>
                )}
            </div>
            )}
        </div>
    );
};

export default QueueStatus;
