import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { cancelImport, getImportProgress, startOpenWebUIImport } from "../services/api";

// Constants
const POLL_INTERVAL_MS = 1000; // Poll progress every second
const MAX_POLL_FAILURES = 5; // Stop polling after this many consecutive failures

const ImportPage: React.FC = () => {
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [targetUserId, setTargetUserId] = useState<string>("");
    const [openwebuiUserId, setOpenwebuiUserId] = useState<string>("");
    const [afterDate, setAfterDate] = useState<string>("");
    const [batchSize, setBatchSize] = useState<number>(10);
    const [limit, setLimit] = useState<string>("");
    const [dryRun, setDryRun] = useState<boolean>(true);

    const [importing, setImporting] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    // Progress state
    const [progress, setProgress] = useState<any>(null);
    const [polling, setPolling] = useState<boolean>(false);
    // @ts-ignore - pollFailureCount is used in setPollFailureCount callback
    const [pollFailureCount, setPollFailureCount] = useState<number>(0);

    // Poll for progress updates
    useEffect(() => {
        let interval: NodeJS.Timeout | null = null;

        if (polling) {
            interval = setInterval(async () => {
                try {
                    const result = await getImportProgress();

                    // Reset failure count on successful response
                    setPollFailureCount(0);

                    if (result.success && result.progress) {
                        // Never reset progress to null once we've started importing
                        // This prevents flickering when transitioning from idle to initializing
                        if (result.progress.status === 'idle' && result.progress.total_conversations === 0 && !importing) {
                            // Only reset to null if we're truly not in an import session
                            setProgress(null);
                        } else {
                            // Always update progress - use a state update function to ensure we never go backwards
                            setProgress((prevProgress: any) => {
                                // Prevent ALL numeric counters from decreasing AND status from reverting
                                if (prevProgress && result.progress) {
                                    // Status priority: idle < initializing < running < completed/failed/cancelled
                                    // Never let status revert to an earlier state
                                    const statusPriority: any = {
                                        'idle': 0,
                                        'initializing': 1,
                                        'running': 2,
                                        'completed': 3,
                                        'failed': 3,
                                        'cancelled': 3
                                    };

                                    const prevPriority = statusPriority[prevProgress.status] || 0;
                                    const newPriority = statusPriority[result.progress.status] || 0;
                                    const effectiveStatus = newPriority >= prevPriority ? result.progress.status : prevProgress.status;

                                    return {
                                        ...result.progress,
                                        status: effectiveStatus,
                                        // Preserve dry_run - once true, stays true for the session
                                        dry_run: prevProgress.dry_run || result.progress.dry_run,
                                        total_conversations: Math.max(prevProgress.total_conversations || 0, result.progress.total_conversations || 0),
                                        processed_conversations: Math.max(prevProgress.processed_conversations || 0, result.progress.processed_conversations || 0),
                                        extracted_memories: Math.max(prevProgress.extracted_memories || 0, result.progress.extracted_memories || 0),
                                        failed_conversations: Math.max(prevProgress.failed_conversations || 0, result.progress.failed_conversations || 0),
                                        elapsed_seconds: Math.max(prevProgress.elapsed_seconds || 0, result.progress.elapsed_seconds || 0),
                                        progress_percentage: Math.max(prevProgress.progress_percentage || 0, result.progress.progress_percentage || 0),
                                    };
                                }
                                return result.progress;
                            });
                        }

                        // Stop polling if import completed, failed, or cancelled
                        if (['completed', 'failed', 'cancelled'].includes(result.progress.status)) {
                            // Wait a bit before stopping polling to ensure we have the final state
                            setTimeout(() => {
                                setPolling(false);
                                setImporting(false);
                            }, 500);

                            if (result.progress.status === 'completed') {
                                setSuccess(
                                    `Import completed! Processed ${result.progress.processed_conversations} conversations and extracted ${result.progress.extracted_memories} memories.`
                                );
                                setError(null);
                            } else if (result.progress.status === 'failed') {
                                setError(result.progress.error_message || 'Import failed');
                                setSuccess(null);
                            } else if (result.progress.status === 'cancelled') {
                                setSuccess(null);
                                setError(`Import cancelled. Processed ${result.progress.processed_conversations} of ${result.progress.total_conversations} conversations (${result.progress.extracted_memories} memories extracted)`);
                            }
                        }
                    }
                } catch (err) {
                    console.error('Error polling progress:', err);
                    setPollFailureCount(prev => {
                        const newCount = prev + 1;

                        // Stop polling after MAX_POLL_FAILURES consecutive failures
                        if (newCount >= MAX_POLL_FAILURES) {
                            setPolling(false);
                            setImporting(false);
                            setError('Lost connection to server. Please refresh the page and check import status.');
                        }

                        return newCount;
                    });
                }
            }, POLL_INTERVAL_MS);
        }

        return () => {
            if (interval) {
                clearInterval(interval);
            }
        };
    }, [polling, importing]);

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files && event.target.files[0]) {
            setSelectedFile(event.target.files[0]);
            setError(null);
            setSuccess(null);
        }
    };

    const handleStartImport = async () => {
        if (!selectedFile) {
            setError('Please select a database file');
            return;
        }

        // Reset all state before starting new import
        setError(null);
        setSuccess(null);
        setProgress(null);
        setPollFailureCount(0);
        setImporting(true);

        try {
            const result = await startOpenWebUIImport(selectedFile, {
                target_user_id: targetUserId || undefined,
                openwebui_user_id: openwebuiUserId || undefined,
                after_date: afterDate || undefined,
                batch_size: batchSize,
                limit: limit ? parseInt(limit) : undefined,
                dry_run: dryRun,
            });

            if (result.success) {
                setSuccess(result.message || 'Import started successfully');
                setPolling(true); // Start polling for progress
            } else {
                setError(result.error || 'Failed to start import');
                setImporting(false);
            }
        } catch (err) {
            const errorMessage = err instanceof Error
                ? err.message
                : 'An unexpected error occurred while starting the import';
            setError(errorMessage);
            setImporting(false);
            console.error('Import start error:', err);
        }
    };

    const handleCancelImport = async () => {
        try {
            setSuccess('Cancelling import... (will stop after current conversation completes)');
            const result = await cancelImport();
            if (result.success) {
                // Success message will be updated by polling when status changes
            } else {
                setError(result.error || 'Failed to cancel import');
            }
        } catch (err) {
            const errorMessage = err instanceof Error
                ? err.message
                : 'Failed to cancel import';
            setError(errorMessage);
            console.error('Cancel import error:', err);
        }
    };

    const handleReset = () => {
        setSelectedFile(null);
        setTargetUserId("");
        setOpenwebuiUserId("");
        setAfterDate("");
        setLimit("");
        setDryRun(true);
        setError(null);
        setSuccess(null);
        setProgress(null);
        setImporting(false);
        setPolling(false);
    };

    const formatElapsedTime = (seconds: number | null) => {
        if (seconds === null || seconds === undefined) return 'N/A';

        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);

        if (hours > 0) {
            return `${hours}h ${mins}m ${secs}s`;
        }
        return `${mins}m ${secs}s`;
    };

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Header */}
            <header className="bg-white shadow-sm">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center py-6">
                        <div className="flex items-center">
                            <h1 className="text-3xl font-bold text-gray-900">
                                Import Open WebUI History
                            </h1>
                            <span className="ml-3 text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                                Beta
                            </span>
                        </div>
                        <Link
                            to="/"
                            className="inline-flex items-center px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors duration-200"
                        >
                            <svg
                                className="mr-2 w-4 h-4"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M10 19l-7-7m0 0l7-7m-7 7h18"
                                />
                            </svg>
                            Back to Home
                        </Link>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Description */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-8">
                    <h2 className="text-lg font-semibold text-blue-900 mb-2">
                        📚 Import Historical Conversations
                    </h2>
                    <p className="text-blue-800 mb-3">
                        Upload your Open WebUI database file (webui.db) to extract and import memories from your existing conversations.
                    </p>
                    <div className="text-sm text-blue-700">
                        <p className="mb-2"><strong>How to get your database file:</strong></p>
                        <code className="bg-blue-100 px-2 py-1 rounded text-xs block mb-2">
                            docker cp open-webui:/app/backend/data/webui.db ./webui.db
                        </code>
                        <p className="text-xs text-blue-600">
                            💡 Tip: Start with "Dry Run" mode to preview what will be imported before committing.
                        </p>
                    </div>
                </div>

                <div className="grid lg:grid-cols-2 gap-8">
                    {/* Import Configuration */}
                    <div className="bg-white rounded-lg shadow-md">
                        <div className="px-6 py-4 border-b border-gray-200">
                            <h2 className="text-xl font-bold text-gray-900">
                                Import Configuration
                            </h2>
                        </div>

                        <div className="p-6 space-y-4">
                            {/* File Upload */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Database File *
                                </label>
                                <input
                                    type="file"
                                    accept=".db"
                                    onChange={handleFileChange}
                                    disabled={importing}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                                />
                                {selectedFile && (
                                    <p className="mt-2 text-sm text-gray-600">
                                        Selected: {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
                                    </p>
                                )}
                            </div>

                            {/* Dry Run Toggle */}
                            <div className="flex items-center space-x-3 bg-yellow-50 border border-yellow-200 rounded-md p-4">
                                <input
                                    type="checkbox"
                                    id="dryRun"
                                    checked={dryRun}
                                    onChange={(e) => setDryRun(e.target.checked)}
                                    disabled={importing}
                                    className="w-4 h-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                                />
                                <label htmlFor="dryRun" className="flex-1 text-sm font-medium text-gray-900">
                                    Dry Run Mode (Preview Only)
                                </label>
                            </div>

                            {/* Target User ID */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Target Mnemosyne User ID (Optional)
                                </label>
                                <input
                                    type="text"
                                    value={targetUserId}
                                    onChange={(e) => setTargetUserId(e.target.value)}
                                    placeholder="Assign all memories to this UUID"
                                    disabled={importing}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                                />
                                <p className="mt-1 text-xs text-gray-500">
                                    Leave empty to map Open WebUI user IDs automatically
                                </p>
                            </div>

                            {/* Open WebUI User Filter */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Filter by Open WebUI User ID (Optional)
                                </label>
                                <input
                                    type="text"
                                    value={openwebuiUserId}
                                    onChange={(e) => setOpenwebuiUserId(e.target.value)}
                                    placeholder="Only import conversations from this user"
                                    disabled={importing}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                                />
                            </div>

                            {/* Date Filter */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Import After Date (Optional)
                                </label>
                                <input
                                    type="date"
                                    value={afterDate}
                                    onChange={(e) => setAfterDate(e.target.value)}
                                    disabled={importing}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:bg-gray-50 disabled:cursor-not-allowed text-gray-700 [&::-webkit-calendar-picker-indicator]:cursor-pointer [&::-webkit-calendar-picker-indicator]:opacity-60 hover:[&::-webkit-calendar-picker-indicator]:opacity-100"
                                />
                            </div>

                            {/* Advanced Options */}
                            <details className="border border-gray-200 rounded-md">
                                <summary className="px-4 py-2 cursor-pointer hover:bg-gray-50 text-sm font-medium text-gray-700">
                                    Advanced Options
                                </summary>
                                <div className="px-4 py-3 space-y-3 border-t border-gray-200">
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-2">
                                            Batch Size
                                        </label>
                                        <input
                                            type="number"
                                            value={batchSize}
                                            onChange={(e) => setBatchSize(parseInt(e.target.value) || 10)}
                                            min="1"
                                            max="100"
                                            disabled={importing}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                                        />
                                        <p className="mt-1 text-xs text-gray-500">
                                            Conversations processed per batch (1-100)
                                        </p>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-2">
                                            Limit (Optional)
                                        </label>
                                        <input
                                            type="number"
                                            value={limit}
                                            onChange={(e) => setLimit(e.target.value)}
                                            placeholder="No limit"
                                            min="1"
                                            disabled={importing}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                                        />
                                        <p className="mt-1 text-xs text-gray-500">
                                            Maximum conversations to import (leave empty for all)
                                        </p>
                                    </div>
                                </div>
                            </details>

                            {/* Action Buttons */}
                            <div className="flex space-x-3 pt-4">
                                <button
                                    onClick={handleStartImport}
                                    disabled={importing || !selectedFile}
                                    className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                >
                                    {importing ? 'Importing...' : dryRun ? 'Preview Import (Dry Run)' : 'Start Import'}
                                </button>
                                <button
                                    onClick={handleReset}
                                    disabled={importing}
                                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                >
                                    Reset
                                </button>
                            </div>

                            {/* Status Messages */}
                            {error && (
                                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                                    <p className="text-red-800 text-sm">{error}</p>
                                </div>
                            )}

                            {success && (
                                <div className="bg-green-50 border border-green-200 rounded-md p-4">
                                    <p className="text-green-800 text-sm">{success}</p>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Progress Panel */}
                    <div className="bg-white rounded-lg shadow-md">
                        <div className="px-6 py-4 border-b border-gray-200">
                            <h2 className="text-xl font-bold text-gray-900">
                                Import Progress
                            </h2>
                        </div>

                        <div className="p-6">
                            {!progress || (progress.status === 'idle' && !importing) ? (
                                <div className="text-center py-12">
                                    <svg className="mx-auto w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                    <p className="text-gray-500">No import in progress</p>
                                    <p className="text-sm text-gray-400 mt-2">
                                        Configure and start an import to see progress here
                                    </p>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {/* Status Badge */}
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm font-medium text-gray-700">Status:</span>
                                        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                                            progress.status === 'initializing' ? 'bg-indigo-100 text-indigo-800' :
                                            progress.status === 'running' ? 'bg-blue-100 text-blue-800' :
                                            progress.status === 'completed' ? 'bg-green-100 text-green-800' :
                                            progress.status === 'failed' ? 'bg-red-100 text-red-800' :
                                            progress.status === 'cancelled' ? 'bg-yellow-100 text-yellow-800' :
                                            'bg-gray-100 text-gray-800'
                                        }`}>
                                            {progress.status.charAt(0).toUpperCase() + progress.status.slice(1)}
                                        </span>
                                    </div>

                                    {/* Progress Bar */}
                                    <div>
                                        <div className="flex justify-between items-center mb-2">
                                            <span className="text-sm font-medium text-gray-700">Progress</span>
                                            <span className="text-sm text-gray-600">{progress.progress_percentage}%</span>
                                        </div>
                                        <div className="w-full bg-gray-200 rounded-full h-4">
                                            <div
                                                className={`h-4 rounded-full transition-all duration-300 ${
                                                    progress.status === 'completed' ? 'bg-green-500' :
                                                    progress.status === 'failed' ? 'bg-red-500' :
                                                    'bg-blue-500'
                                                }`}
                                                style={{ width: `${progress.progress_percentage}%` }}
                                            />
                                        </div>
                                    </div>

                                    {/* Statistics */}
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="bg-gray-50 rounded-md p-3">
                                            <p className="text-xs text-gray-500 mb-1">Conversations</p>
                                            <p className="text-2xl font-bold text-gray-900">
                                                {progress.processed_conversations} / {progress.total_conversations}
                                            </p>
                                        </div>
                                        <div className="bg-green-50 rounded-md p-3">
                                            <p className="text-xs text-green-600 mb-1">Memories Extracted</p>
                                            <p className="text-2xl font-bold text-green-700">
                                                {progress.extracted_memories}
                                            </p>
                                        </div>
                                        <div className="bg-red-50 rounded-md p-3">
                                            <p className="text-xs text-red-600 mb-1">Failed</p>
                                            <p className="text-2xl font-bold text-red-700">
                                                {progress.failed_conversations}
                                            </p>
                                        </div>
                                        <div className="bg-blue-50 rounded-md p-3">
                                            <p className="text-xs text-blue-600 mb-1">Elapsed Time</p>
                                            <p className="text-lg font-bold text-blue-700">
                                                {formatElapsedTime(progress.elapsed_seconds)}
                                            </p>
                                        </div>
                                    </div>

                                    {/* Current Conversation - Always visible, never flashes */}
                                    <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
                                        <p className="text-xs text-blue-600 mb-1">
                                            {progress.status === 'initializing' ? 'Status:' : 'Processing:'}
                                        </p>
                                        <p className="text-sm text-blue-800 font-mono truncate">
                                            {progress.status === 'initializing'
                                                ? 'Initializing import...'
                                                : progress.current_conversation_id || 'Waiting for next conversation...'}
                                        </p>
                                    </div>

                                    {/* Error Message */}
                                    {progress.error_message && (
                                        <div className="bg-red-50 border border-red-200 rounded-md p-3">
                                            <p className="text-xs text-red-600 mb-1">Error:</p>
                                            <p className="text-sm text-red-800">{progress.error_message}</p>
                                        </div>
                                    )}

                                    {/* Dry Run Notice - Always visible during dry run, never flashes */}
                                    {progress.dry_run && (
                                        <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
                                            <p className="text-sm text-yellow-800">
                                                🔍 <strong>Dry Run Mode:</strong> No memories are being saved
                                            </p>
                                        </div>
                                    )}

                                    {/* Cancel Button */}
                                    {progress.status === 'running' && (
                                        <button
                                            onClick={handleCancelImport}
                                            className="w-full px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
                                        >
                                            Cancel Import
                                        </button>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
};

export default ImportPage;
