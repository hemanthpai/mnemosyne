import React, { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import { useSidebar } from '../contexts/SidebarContext';
import { cancelBenchmark, getBenchmarkResults, getBenchmarkStatus, listDatasets, runBenchmark, uploadDataset } from '../services/api';

interface Dataset {
    filename: string;
    description: string;
    version: string;
    num_conversations: number;
    num_queries: number;
}

interface BenchmarkProgress {
    current: number;
    total: number;
    phase: string;
    percentage: number;
}

interface BenchmarkStatus {
    task_id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    test_type?: string;
    dataset?: string;
    progress?: BenchmarkProgress;
}

const BenchmarksPage: React.FC = () => {
    const { isSidebarOpen } = useSidebar();
    const [testType, setTestType] = useState<string>('all');
    const [selectedDataset, setSelectedDataset] = useState<string>('benchmark_dataset.json');
    const [datasets, setDatasets] = useState<Dataset[]>([]);
    const [loading, setLoading] = useState(false);
    const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
    const [benchmarkStatus, setBenchmarkStatus] = useState<BenchmarkStatus | null>(null);
    const [results, setResults] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [uploadLoading, setUploadLoading] = useState(false);
    const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
    const [uploadError, setUploadError] = useState<string | null>(null);

    const STORAGE_KEY = 'mnemosyne_active_benchmark';

    // Load available datasets and check for active benchmark on mount
    useEffect(() => {
        loadDatasets();
        checkForActiveBenchmark();
    }, []);

    // Check for an active benchmark in localStorage and resume monitoring
    const checkForActiveBenchmark = async () => {
        const storedTaskId = localStorage.getItem(STORAGE_KEY);
        if (!storedTaskId) return;

        try {
            // Check if this benchmark is still active
            const response = await getBenchmarkStatus(storedTaskId);
            if (response.success && (response.status === 'pending' || response.status === 'running')) {
                // Resume monitoring this benchmark
                setCurrentTaskId(storedTaskId);
                setBenchmarkStatus(response);
                setLoading(true);
                console.log(`Resuming monitoring of benchmark: ${storedTaskId}`);
            } else {
                // Benchmark is completed/failed, clear it from storage
                localStorage.removeItem(STORAGE_KEY);
            }
        } catch (err) {
            // If we can't fetch the status, clear the stored task
            console.error('Error checking stored benchmark:', err);
            localStorage.removeItem(STORAGE_KEY);
        }
    };

    // Poll for benchmark status when a task is running
    useEffect(() => {
        if (!currentTaskId) return;

        const interval = setInterval(async () => {
            try {
                const response = await getBenchmarkStatus(currentTaskId);
                if (response.success) {
                    setBenchmarkStatus(response);

                    if (response.status === 'completed') {
                        // Fetch full results
                        try {
                            const resultsResponse = await getBenchmarkResults(currentTaskId);
                            if (resultsResponse.success && resultsResponse.output) {
                                setResults(resultsResponse.output);
                            } else {
                                setError(resultsResponse.error || 'No results available');
                            }
                        } catch (err: any) {
                            console.error('Error fetching results:', err);
                            setError('Failed to fetch benchmark results');
                        }
                        setLoading(false);
                        setCurrentTaskId(null);
                        localStorage.removeItem(STORAGE_KEY); // Clear from storage on completion
                        clearInterval(interval);
                    } else if (response.status === 'failed') {
                        setError('Benchmark failed');
                        setLoading(false);
                        setCurrentTaskId(null);
                        localStorage.removeItem(STORAGE_KEY); // Clear from storage on failure
                        clearInterval(interval);
                    }
                }
            } catch (err: any) {
                console.error('Error polling benchmark status:', err);
            }
        }, 2000); // Poll every 2 seconds

        return () => clearInterval(interval);
    }, [currentTaskId]);

    const loadDatasets = async () => {
        try {
            const response = await listDatasets();
            if (response.success) {
                setDatasets(response.datasets);

                // If the default dataset doesn't exist in the list, select the first available one
                if (response.datasets.length > 0) {
                    const defaultExists = response.datasets.some((d: Dataset) => d.filename === 'benchmark_dataset.json');
                    if (!defaultExists) {
                        setSelectedDataset(response.datasets[0].filename);
                    }
                }
            }
        } catch (err: any) {
            console.error('Error loading datasets:', err);
        }
    };

    const handleRunBenchmark = async () => {
        setError(null);
        setResults(null);
        setLoading(true);
        setBenchmarkStatus(null);

        try {
            const response = await runBenchmark(testType, selectedDataset);
            if (response.success) {
                setCurrentTaskId(response.task_id);
                // Store task ID in localStorage for resume capability
                localStorage.setItem(STORAGE_KEY, response.task_id);
            } else {
                setError(response.error || 'Failed to start benchmark');
                setLoading(false);
            }
        } catch (err: any) {
            setError(err.message || 'Failed to start benchmark');
            setLoading(false);
        }
    };

    const handleClearStuckTask = () => {
        if (!window.confirm('Clear stuck benchmark task? This will reset the benchmark runner.')) {
            return;
        }

        // Clear everything
        localStorage.removeItem(STORAGE_KEY);
        setCurrentTaskId(null);
        setBenchmarkStatus(null);
        setLoading(false);
        setResults(null);
        setError(null);
    };

    const handleCancelBenchmark = async () => {
        if (!currentTaskId) return;

        if (!window.confirm('Cancel this benchmark run? This will stop the running benchmark.')) {
            return;
        }

        try {
            setLoading(false);
            const resp = await cancelBenchmark(currentTaskId);
            if (resp && resp.success) {
                // Clear local tracking state and show a cancelled status
                localStorage.removeItem(STORAGE_KEY);
                setCurrentTaskId(null);
                setBenchmarkStatus((prev) => prev ? { ...prev, status: 'failed' } : null);
                setError('Benchmark cancelled by user');
            } else {
                setError(resp?.error || 'Failed to cancel benchmark');
            }
        } catch (err: any) {
            console.error('Error cancelling benchmark:', err);
            setError(err?.message || 'Failed to cancel benchmark');
        }
    };

    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        // Validate file type
        if (!file.name.endsWith('.json')) {
            setUploadError('Please select a JSON file (.json)');
            return;
        }

        setUploadLoading(true);
        setUploadError(null);
        setUploadSuccess(null);

        try {
            const response = await uploadDataset(file);
            if (response.success) {
                setUploadSuccess(`Successfully uploaded "${response.filename}" (${response.num_conversations} conversations, ${response.num_queries} queries)`);
                // Reload datasets list
                await loadDatasets();
                // Select the newly uploaded dataset
                setSelectedDataset(response.filename);
                // Clear the file input
                event.target.value = '';
            } else {
                setUploadError(response.error || 'Failed to upload dataset');
            }
        } catch (err: any) {
            if (err.response?.data?.error) {
                setUploadError(err.response.data.error);
            } else {
                setUploadError(err.message || 'Failed to upload dataset');
            }
        } finally {
            setUploadLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
            <PageHeader
                title="Benchmark Dashboard"
                subtitle="Run benchmark tests to evaluate extraction and search quality"
            />

            <div className={`transition-all duration-300 ${isSidebarOpen ? 'ml-60' : 'ml-0'}`}>
                <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

                    {/* Upload Dataset Section */}
                    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 mb-6">
                        <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-4">
                            Upload New Dataset
                        </h2>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                    Select JSON dataset file
                                </label>
                                <input
                                    type="file"
                                    accept=".json"
                                    onChange={handleFileUpload}
                                    disabled={uploadLoading}
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                                />
                                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                    Upload a benchmark dataset in JSON format
                                </p>
                            </div>

                            {uploadLoading && (
                                <div className="flex items-center text-blue-600 dark:text-blue-400">
                                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mr-2"></div>
                                    <span className="text-sm">Uploading...</span>
                                </div>
                            )}

                            {uploadSuccess && (
                                <div className="bg-green-50 dark:bg-green-900 border border-green-200 dark:border-green-700 rounded-md p-3">
                                    <p className="text-sm text-green-800 dark:text-green-100">{uploadSuccess}</p>
                                </div>
                            )}

                            {uploadError && (
                                <div className="bg-red-50 dark:bg-red-900 border border-red-200 dark:border-red-700 rounded-md p-3">
                                    <p className="text-sm text-red-800 dark:text-red-100">{uploadError}</p>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Configuration Section */}
                    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 mb-6">
                        <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-4">
                            Configure Benchmark
                        </h2>

                        <div className="space-y-4">
                            {/* Test Type Selection */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                    Test Type
                                </label>
                                <select
                                    value={testType}
                                    onChange={(e) => setTestType(e.target.value)}
                                    disabled={loading}
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                >
                                    <option value="all">All Tests</option>
                                    <option value="extraction">Extraction Only</option>
                                    <option value="search">Search Only</option>
                                    <option value="evolution">Evolution Only</option>
                                </select>
                            </div>

                            {/* Dataset Selection */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                    Dataset
                                </label>
                                <select
                                    value={selectedDataset}
                                    onChange={(e) => setSelectedDataset(e.target.value)}
                                    disabled={loading}
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                                >
                                    {datasets.map((dataset) => (
                                        <option key={dataset.filename} value={dataset.filename} className="py-1">
                                            {dataset.filename} ({dataset.num_conversations} {dataset.num_conversations === 1 ? 'conversation' : 'conversations'})
                                        </option>
                                    ))}
                                </select>
                                {datasets.length === 0 && (
                                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                                        No datasets found
                                    </p>
                                )}
                                {selectedDataset && datasets.length > 0 && (
                                    <p className="mt-2 text-xs text-gray-600 dark:text-gray-400">
                                        {datasets.find(d => d.filename === selectedDataset)?.description}
                                    </p>
                                )}
                            </div>

                            {/* Action Buttons */}
                            <div className="flex gap-3">
                                <button
                                    onClick={handleRunBenchmark}
                                    disabled={loading || datasets.length === 0}
                                    className={`flex-1 px-6 py-3 rounded-md text-white font-medium ${loading || datasets.length === 0
                                            ? 'bg-gray-400 cursor-not-allowed'
                                            : 'bg-blue-600 hover:bg-blue-700'
                                        }`}
                                >
                                    {loading ? 'Running Benchmark...' : 'Run Benchmark'}
                                </button>

                                {(loading || currentTaskId) && (
                                    <>
                                        <button
                                            onClick={handleClearStuckTask}
                                            className="px-4 py-3 bg-red-600 text-white rounded-md hover:bg-red-700 font-medium whitespace-nowrap"
                                            title="Clear stuck or pending task"
                                        >
                                            Clear Task
                                        </button>

                                        {/* Cancel button: shown when there is an active task */}
                                        {currentTaskId && (
                                            <button
                                                onClick={handleCancelBenchmark}
                                                className="px-4 py-3 bg-yellow-600 text-white rounded-md hover:bg-yellow-700 font-medium whitespace-nowrap"
                                                title="Cancel running benchmark"
                                            >
                                                Cancel Benchmark
                                            </button>
                                        )}
                                    </>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Status Section */}
                    {(loading || benchmarkStatus) && (
                        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 mb-6">
                            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-4">
                                Status
                            </h2>

                            {loading && !benchmarkStatus && (
                                <div className="flex items-center justify-center py-4">
                                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3"></div>
                                    <span className="text-gray-600 dark:text-gray-400">Starting benchmark...</span>
                                </div>
                            )}

                            {benchmarkStatus && (
                                <div className="space-y-2">
                                    <div className="flex items-center">
                                        <span className="text-sm font-medium text-gray-700 dark:text-gray-300 w-32">Task ID:</span>
                                        <span className="text-sm text-gray-600 dark:text-gray-400 font-mono">{benchmarkStatus.task_id}</span>
                                    </div>
                                    <div className="flex items-center">
                                        <span className="text-sm font-medium text-gray-700 dark:text-gray-300 w-32">Status:</span>
                                        <span className={`text-sm px-2 py-1 rounded ${benchmarkStatus.status === 'completed' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100' :
                                                benchmarkStatus.status === 'failed' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100' :
                                                    'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100'
                                            }`}>
                                            {benchmarkStatus.status}
                                        </span>
                                    </div>
                                    {loading && (benchmarkStatus.status === 'pending' || benchmarkStatus.status === 'running') && (
                                        <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-md border border-blue-200 dark:border-blue-800">
                                            <div className="flex items-center">
                                                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600 mr-3"></div>
                                                <div className="flex-1">
                                                    <span className="text-sm font-medium text-blue-900 dark:text-blue-100 block">
                                                        {benchmarkStatus.progress?.phase || 'Running benchmark tests...'}
                                                    </span>
                                                    <span className="text-xs text-blue-700 dark:text-blue-300 mt-1 block">
                                                        This may take a few minutes. Status updates every 2 seconds.
                                                    </span>
                                                </div>
                                            </div>

                                            {benchmarkStatus.progress && (
                                                <div className="mt-3">
                                                    <div className="flex justify-between text-xs text-blue-700 dark:text-blue-300 mb-1">
                                                        <span>{benchmarkStatus.progress.current} / {benchmarkStatus.progress.total} tests</span>
                                                        <span>{benchmarkStatus.progress.percentage}%</span>
                                                    </div>
                                                    <div className="w-full bg-blue-200 dark:bg-blue-800 rounded-full h-2">
                                                        <div
                                                            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                                                            style={{ width: `${benchmarkStatus.progress.percentage}%` }}
                                                        ></div>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Error Display */}
                    {error && (
                        <div className="bg-red-50 dark:bg-red-900 border border-red-200 dark:border-red-700 rounded-lg p-4 mb-6">
                            <p className="text-red-800 dark:text-red-100">{error}</p>
                        </div>
                    )}

                    {/* Results Section */}
                    {results && (
                        <div className="space-y-6">
                            {/* Extraction Results */}
                            {results.includes('Extraction Quality:') && (
                                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
                                    <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
                                        <span>📊</span> Extraction Quality
                                    </h2>

                                    {(() => {
                                        // Parse extraction metrics
                                        const precisionMatch = results.match(/Precision:\s+([\d.]+)%/);
                                        const recallMatch = results.match(/Recall:\s+([\d.]+)%/);
                                        const f1Match = results.match(/F1 Score:\s+([\d.]+)%/);
                                        const fprMatch = results.match(/False Positive Rate:\s+([\d.]+)%/);
                                        const qualityMatch = results.match(/Overall Quality:\s+(\w+)/);

                                        const precision = precisionMatch ? parseFloat(precisionMatch[1]) : 0;
                                        const recall = recallMatch ? parseFloat(recallMatch[1]) : 0;
                                        const f1 = f1Match ? parseFloat(f1Match[1]) : 0;
                                        const fpr = fprMatch ? parseFloat(fprMatch[1]) : 0;
                                        const quality = qualityMatch ? qualityMatch[1] : 'UNKNOWN';

                                        const getQualityColor = (q: string) => {
                                            if (q.includes('EXCELLENT')) return 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-100 border-green-300 dark:border-green-700';
                                            if (q.includes('GOOD')) return 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100 border-blue-300 dark:border-blue-700';
                                            if (q.includes('FAIR')) return 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-100 border-yellow-300 dark:border-yellow-700';
                                            return 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 border-red-300 dark:border-red-700';
                                        };

                                        const getMetricColor = (value: number, type: 'good' | 'bad' = 'good') => {
                                            if (type === 'bad') {
                                                if (value < 5) return 'text-green-600 dark:text-green-400';
                                                if (value < 15) return 'text-yellow-600 dark:text-yellow-400';
                                                return 'text-red-600 dark:text-red-400';
                                            }
                                            if (value >= 90) return 'text-green-600 dark:text-green-400';
                                            if (value >= 70) return 'text-blue-600 dark:text-blue-400';
                                            if (value >= 50) return 'text-yellow-600 dark:text-yellow-400';
                                            return 'text-red-600 dark:text-red-400';
                                        };

                                        return (
                                            <>
                                                {/* Overall Quality Badge */}
                                                <div className={`mb-4 p-4 border-2 rounded-lg ${getQualityColor(quality)}`}>
                                                    <div className="flex items-center justify-between">
                                                        <span className="text-lg font-semibold">Overall Quality:</span>
                                                        <span className="text-2xl font-bold">{quality}</span>
                                                    </div>
                                                </div>

                                                {/* Metrics Grid */}
                                                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                                                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Precision</p>
                                                        <p className={`text-3xl font-bold ${getMetricColor(precision)}`}>{precision.toFixed(1)}%</p>
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Accuracy of extracted notes</p>
                                                    </div>
                                                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Recall</p>
                                                        <p className={`text-3xl font-bold ${getMetricColor(recall)}`}>{recall.toFixed(1)}%</p>
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Coverage of ground truth</p>
                                                    </div>
                                                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">F1 Score</p>
                                                        <p className={`text-3xl font-bold ${getMetricColor(f1)}`}>{f1.toFixed(1)}%</p>
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Harmonic mean P & R</p>
                                                    </div>
                                                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">False Positive Rate</p>
                                                        <p className={`text-3xl font-bold ${getMetricColor(fpr, 'bad')}`}>{fpr.toFixed(1)}%</p>
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Incorrect extractions</p>
                                                    </div>
                                                </div>

                                                {/* Category Breakdown */}
                                                {results.includes('By Category:') && (() => {
                                                    const categorySection = results.split('By Category:')[1]?.split('\n\n')[0];
                                                    if (categorySection) {
                                                        const categoryLines = categorySection.split('\n').filter(line => line.includes('P='));
                                                        const categories = categoryLines.map(line => {
                                                            const match = line.match(/(\w+(?::\w+)?)\s*:\s*P=([\d.]+)%\s*R=([\d.]+)%\s*F1=([\d.]+)%/);
                                                            if (match) {
                                                                return {
                                                                    name: match[1].trim(),
                                                                    precision: parseFloat(match[2]),
                                                                    recall: parseFloat(match[3]),
                                                                    f1: parseFloat(match[4])
                                                                };
                                                            }
                                                            return null;
                                                        }).filter(Boolean);

                                                        if (categories.length > 0) {
                                                            return (
                                                                <div className="mt-6">
                                                                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">By Category</h3>
                                                                    <div className="overflow-x-auto">
                                                                        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                                                                            <thead className="bg-gray-50 dark:bg-gray-700">
                                                                                <tr>
                                                                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Category</th>
                                                                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Precision</th>
                                                                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Recall</th>
                                                                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">F1</th>
                                                                                </tr>
                                                                            </thead>
                                                                            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                                                                                {categories.map((cat: any, idx: number) => (
                                                                                    <tr key={idx}>
                                                                                        <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{cat.name}</td>
                                                                                        <td className={`px-4 py-3 text-sm text-right font-semibold ${getMetricColor(cat.precision)}`}>{cat.precision.toFixed(1)}%</td>
                                                                                        <td className={`px-4 py-3 text-sm text-right font-semibold ${getMetricColor(cat.recall)}`}>{cat.recall.toFixed(1)}%</td>
                                                                                        <td className={`px-4 py-3 text-sm text-right font-semibold ${getMetricColor(cat.f1)}`}>{cat.f1.toFixed(1)}%</td>
                                                                                    </tr>
                                                                                ))}
                                                                            </tbody>
                                                                        </table>
                                                                    </div>
                                                                </div>
                                                            );
                                                        }
                                                    }
                                                    return null;
                                                })()}
                                            </>
                                        );
                                    })()}
                                </div>
                            )}

                            {/* Search Results */}
                            {results.includes('Search Quality:') && (
                                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
                                    <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
                                        <span>🔍</span> Search Quality
                                    </h2>

                                    {(() => {
                                        // Parse search metrics
                                        const p10Match = results.match(/Precision@10:\s+([\d.]+)%/);
                                        const r10Match = results.match(/Recall@10:\s+([\d.]+)%/);
                                        const mrrMatch = results.match(/MRR:\s+([\d.]+)/);
                                        const qualityMatch = results.split('Search Quality:')[1]?.match(/Overall Quality:\s+(\w+)/);

                                        const p10 = p10Match ? parseFloat(p10Match[1]) : 0;
                                        const r10 = r10Match ? parseFloat(r10Match[1]) : 0;
                                        const mrr = mrrMatch ? parseFloat(mrrMatch[1]) : 0;
                                        const quality = qualityMatch ? qualityMatch[1] : 'UNKNOWN';

                                        const getQualityColor = (q: string) => {
                                            if (q.includes('EXCELLENT')) return 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-100 border-green-300 dark:border-green-700';
                                            if (q.includes('GOOD')) return 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100 border-blue-300 dark:border-blue-700';
                                            if (q.includes('FAIR')) return 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-100 border-yellow-300 dark:border-yellow-700';
                                            return 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 border-red-300 dark:border-red-700';
                                        };

                                        const getMetricColor = (value: number, max: number = 100) => {
                                            const normalized = (value / max) * 100;
                                            if (normalized >= 80) return 'text-green-600 dark:text-green-400';
                                            if (normalized >= 60) return 'text-blue-600 dark:text-blue-400';
                                            if (normalized >= 40) return 'text-yellow-600 dark:text-yellow-400';
                                            return 'text-red-600 dark:text-red-400';
                                        };

                                        return (
                                            <>
                                                {/* Overall Quality Badge */}
                                                <div className={`mb-4 p-4 border-2 rounded-lg ${getQualityColor(quality)}`}>
                                                    <div className="flex items-center justify-between">
                                                        <span className="text-lg font-semibold">Overall Quality:</span>
                                                        <span className="text-2xl font-bold">{quality}</span>
                                                    </div>
                                                </div>

                                                {/* Metrics Grid */}
                                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Precision@10</p>
                                                        <p className={`text-3xl font-bold ${getMetricColor(p10)}`}>{p10.toFixed(1)}%</p>
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Relevant in top 10 results</p>
                                                    </div>
                                                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Recall@10</p>
                                                        <p className={`text-3xl font-bold ${getMetricColor(r10)}`}>{r10.toFixed(1)}%</p>
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Coverage in top 10</p>
                                                    </div>
                                                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">MRR (Mean Reciprocal Rank)</p>
                                                        <p className={`text-3xl font-bold ${getMetricColor(mrr, 1)}`}>{mrr.toFixed(3)}</p>
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">First relevant position</p>
                                                    </div>
                                                </div>
                                            </>
                                        );
                                    })()}
                                </div>
                            )}

                            {/* Evolution Results */}
                            {results.includes('Memory Evolution Quality:') && (
                                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
                                    <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
                                        <span>🧬</span> Memory Evolution Quality
                                    </h2>

                                    {(() => {
                                        // Parse evolution metrics
                                        const notesMatch = results.match(/Notes Tested:\s+(\d+)/);
                                        const evolutionsMatch = results.match(/Evolutions Triggered:\s+(\d+)\s+\(([\d.]+)%\)/);
                                        const neighborsMatch = results.match(/Neighbors Updated:\s+(\d+)/);
                                        const avgMatch = results.match(/Avg Neighbors\/Evolution:\s+([\d.]+)/);
                                        const qualityMatch = results.split('Memory Evolution Quality:')[1]?.match(/Overall Quality:\s+(\w+)/);

                                        const notesTested = notesMatch ? parseInt(notesMatch[1]) : 0;
                                        const evolutions = evolutionsMatch ? parseInt(evolutionsMatch[1]) : 0;
                                        const evolutionRate = evolutionsMatch ? parseFloat(evolutionsMatch[2]) : 0;
                                        const neighbors = neighborsMatch ? parseInt(neighborsMatch[1]) : 0;
                                        const avgNeighbors = avgMatch ? parseFloat(avgMatch[1]) : 0;
                                        const quality = qualityMatch ? qualityMatch[1] : 'UNKNOWN';

                                        const getQualityColor = (q: string) => {
                                            if (q.includes('GOOD')) return 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100 border-blue-300 dark:border-blue-700';
                                            if (q.includes('FAIR')) return 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-100 border-yellow-300 dark:border-yellow-700';
                                            return 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 border-red-300 dark:border-red-700';
                                        };

                                        return (
                                            <>
                                                {/* Overall Quality Badge */}
                                                <div className={`mb-4 p-4 border-2 rounded-lg ${getQualityColor(quality)}`}>
                                                    <div className="flex items-center justify-between">
                                                        <span className="text-lg font-semibold">Overall Quality:</span>
                                                        <span className="text-2xl font-bold">{quality}</span>
                                                    </div>
                                                </div>

                                                {/* Metrics Grid */}
                                                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                                                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Notes Tested</p>
                                                        <p className="text-3xl font-bold text-blue-600 dark:text-blue-400">{notesTested}</p>
                                                    </div>
                                                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Evolutions Triggered</p>
                                                        <p className="text-3xl font-bold text-green-600 dark:text-green-400">{evolutions}</p>
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{evolutionRate.toFixed(1)}% rate</p>
                                                    </div>
                                                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Neighbors Updated</p>
                                                        <p className="text-3xl font-bold text-purple-600 dark:text-purple-400">{neighbors}</p>
                                                    </div>
                                                    <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                                                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Avg per Evolution</p>
                                                        <p className="text-3xl font-bold text-orange-600 dark:text-orange-400">{avgNeighbors.toFixed(1)}</p>
                                                    </div>
                                                </div>
                                            </>
                                        );
                                    })()}
                                </div>
                            )}

                            {/* Raw Output (Collapsible) */}
                            <details className="bg-white dark:bg-gray-800 rounded-lg shadow-md">
                                <summary className="px-6 py-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2">
                                    <span>📄</span> View Raw Output
                                </summary>
                                <div className="px-6 pb-6">
                                    <div className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md p-4 overflow-x-auto">
                                        <pre className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap font-mono">
                                            {results}
                                        </pre>
                                    </div>
                                </div>
                            </details>
                        </div>
                    )}
                </main>
            </div>
        </div>
    );
};

export default BenchmarksPage;
