import React, { useState, useEffect } from 'react';
import { getActiveTasks, getRecentTasks, RunningTask, PendingTask, RecentTask } from '../services/api';
import PageHeader from '../components/PageHeader';
import { useSidebar } from '../contexts/SidebarContext';

const ActivityMonitorPage: React.FC = () => {
    const { isSidebarOpen } = useSidebar();
    const [runningTasks, setRunningTasks] = useState<RunningTask[]>([]);
    const [pendingTasks, setPendingTasks] = useState<PendingTask[]>([]);
    const [recentTasks, setRecentTasks] = useState<RecentTask[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdate, setLastUpdate] = useState<string | null>(null);

    // Fetch tasks data
    const fetchTasks = async () => {
        try {
            const [activeResponse, recentResponse] = await Promise.all([
                getActiveTasks(),
                getRecentTasks()
            ]);

            if (activeResponse.success) {
                setRunningTasks(activeResponse.running);
                setPendingTasks(activeResponse.pending);
                setLastUpdate(new Date(activeResponse.timestamp).toLocaleTimeString());
            }

            if (recentResponse.success) {
                setRecentTasks(recentResponse.tasks);
            }

            setError(null);
        } catch (err: any) {
            console.error('Error fetching tasks:', err);
            setError('Failed to fetch task data');
        } finally {
            setLoading(false);
        }
    };

    // Initial fetch and set up auto-refresh
    useEffect(() => {
        fetchTasks();
        const interval = setInterval(fetchTasks, 2000); // Refresh every 2 seconds

        return () => clearInterval(interval);
    }, []);

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
    };

    const truncateTaskId = (taskId: string): string => {
        return taskId.length > 8 ? `${taskId.slice(0, 8)}...` : taskId;
    };

    const formatElapsedTime = (seconds: number): string => {
        if (seconds < 60) return `${seconds}s`;
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}m ${remainingSeconds}s`;
    };

    const formatDuration = (seconds: number): string => {
        if (seconds < 60) return `${seconds}s`;
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) {
            const remainingSeconds = seconds % 60;
            return `${minutes}m ${remainingSeconds}s`;
        }
        const hours = Math.floor(minutes / 60);
        const remainingMinutes = minutes % 60;
        return `${hours}h ${remainingMinutes}m`;
    };

    const getTaskTypeLabel = (type: string): string => {
        switch (type) {
            case 'extraction': return 'Extraction';
            case 'benchmark': return 'Benchmark';
            default: return 'Unknown';
        }
    };

    const getTaskTypeColor = (type: string): string => {
        switch (type) {
            case 'extraction': return 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200';
            case 'benchmark': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
            default: return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200';
        }
    };

    if (loading && runningTasks.length === 0 && pendingTasks.length === 0 && recentTasks.length === 0) {
        return (
            <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
                <PageHeader
                    title="Activity Monitor"
                    subtitle="Monitor running, pending, and recent tasks"
                />
                <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <div className="flex items-center justify-center py-12">
                        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
                    </div>
                </main>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
            <PageHeader
                title="Activity Monitor"
                subtitle="Monitor running, pending, and recent tasks"
                badge={lastUpdate ? { text: `Updated ${lastUpdate}`, color: 'green' } : undefined}
            />

            <div className={`transition-all duration-300 ${isSidebarOpen ? 'ml-60' : 'ml-0'}`}>
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
                {/* Error Alert */}
                {error && (
                    <div className="bg-red-50 dark:bg-red-900 border border-red-200 dark:border-red-700 rounded-lg p-4">
                        <p className="text-red-800 dark:text-red-100">{error}</p>
                    </div>
                )}

                {/* Running Tasks */}
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md">
                    <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                        <div className="flex items-center justify-between">
                            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                                Running Tasks
                            </h2>
                            <span className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 text-sm px-3 py-1 rounded-full font-medium">
                                {runningTasks.length} active
                            </span>
                        </div>
                    </div>

                    <div className="p-6">
                        {runningTasks.length === 0 ? (
                            <p className="text-gray-500 dark:text-gray-400 text-center py-8">
                                No tasks currently running
                            </p>
                        ) : (
                            <div className="space-y-4">
                                {runningTasks.map((task) => (
                                    <div key={task.task_id} className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                                        <div className="flex items-start justify-between mb-3">
                                            <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <span className={`text-xs px-2 py-1 rounded ${getTaskTypeColor(task.type)}`}>
                                                        {getTaskTypeLabel(task.type)}
                                                    </span>
                                                    <button
                                                        onClick={() => copyToClipboard(task.task_id)}
                                                        className="text-xs text-gray-500 dark:text-gray-400 font-mono hover:text-gray-700 dark:hover:text-gray-200 flex items-center gap-1"
                                                        title="Click to copy full task ID"
                                                    >
                                                        {truncateTaskId(task.task_id)}
                                                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                                        </svg>
                                                    </button>
                                                </div>
                                                <p className="text-sm text-gray-600 dark:text-gray-300 mb-1">
                                                    {task.name}
                                                </p>
                                                {task.progress && (
                                                    <p className="text-sm text-gray-500 dark:text-gray-400">
                                                        {task.progress.phase}
                                                        {task.progress.detail && ` - ${task.progress.detail}`}
                                                    </p>
                                                )}
                                            </div>
                                            <div className="text-sm text-gray-500 dark:text-gray-400">
                                                {formatElapsedTime(task.elapsed_seconds)}
                                            </div>
                                        </div>

                                        {task.progress && (
                                            <div className="mt-2">
                                                <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400 mb-1">
                                                    <span>{task.progress.current} / {task.progress.total}</span>
                                                    <span>{task.progress.percentage}%</span>
                                                </div>
                                                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                                                    <div
                                                        className="bg-green-600 h-2 rounded-full transition-all duration-300"
                                                        style={{ width: `${task.progress.percentage}%` }}
                                                    ></div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Pending Tasks */}
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md">
                    <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                        <div className="flex items-center justify-between">
                            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                                Pending Tasks
                            </h2>
                            <span className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200 text-sm px-3 py-1 rounded-full font-medium">
                                {pendingTasks.length} queued
                            </span>
                        </div>
                    </div>

                    <div className="p-6">
                        {pendingTasks.length === 0 ? (
                            <p className="text-gray-500 dark:text-gray-400 text-center py-8">
                                No tasks in queue
                            </p>
                        ) : (
                            <div className="space-y-3">
                                {pendingTasks.map((task, index) => (
                                    <div key={task.task_id} className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                                        <div className="flex items-center justify-between">
                                            <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className="text-xs text-gray-500 dark:text-gray-400 font-bold">
                                                        #{index + 1}
                                                    </span>
                                                    <span className={`text-xs px-2 py-1 rounded ${getTaskTypeColor(task.type)}`}>
                                                        {getTaskTypeLabel(task.type)}
                                                    </span>
                                                    <button
                                                        onClick={() => copyToClipboard(task.task_id)}
                                                        className="text-xs text-gray-500 dark:text-gray-400 font-mono hover:text-gray-700 dark:hover:text-gray-200 flex items-center gap-1"
                                                        title="Click to copy full task ID"
                                                    >
                                                        {truncateTaskId(task.task_id)}
                                                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2 2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                                        </svg>
                                                    </button>
                                                </div>
                                                <p className="text-sm text-gray-600 dark:text-gray-300">
                                                    {task.name}
                                                </p>
                                            </div>
                                            <div className="text-sm text-gray-500 dark:text-gray-400">
                                                Wait: {formatElapsedTime(task.wait_seconds)}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Recent Tasks */}
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md">
                    <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                        <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                            Recent Tasks
                        </h2>
                    </div>

                    <div className="p-6">
                        {recentTasks.length === 0 ? (
                            <p className="text-gray-500 dark:text-gray-400 text-center py-8">
                                No recent tasks
                            </p>
                        ) : (
                            <div className="space-y-2">
                                {recentTasks.map((task) => (
                                    <div key={task.task_id} className="bg-gray-50 dark:bg-gray-900 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
                                        <div className="flex items-center justify-between">
                                            <div className="flex-1">
                                                <div className="flex items-center gap-2">
                                                    <span className={`text-xs px-2 py-1 rounded ${getTaskTypeColor(task.type)}`}>
                                                        {getTaskTypeLabel(task.type)}
                                                    </span>
                                                    <span className={`text-xs px-2 py-1 rounded ${
                                                        task.status === 'completed'
                                                            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                                            : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                                                    }`}>
                                                        {task.status}
                                                    </span>
                                                    <button
                                                        onClick={() => copyToClipboard(task.task_id)}
                                                        className="text-xs text-gray-500 dark:text-gray-400 font-mono hover:text-gray-700 dark:hover:text-gray-200 flex items-center gap-1"
                                                        title="Click to copy full task ID"
                                                    >
                                                        {truncateTaskId(task.task_id)}
                                                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                                        </svg>
                                                    </button>
                                                    <span className="text-xs text-gray-500 dark:text-gray-400">
                                                        {task.name}
                                                    </span>
                                                </div>
                                            </div>
                                            <div className="text-xs text-gray-500 dark:text-gray-400">
                                                Duration: {formatDuration(task.duration_seconds)}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </main>
            </div>
        </div>
    );
};

export default ActivityMonitorPage;
