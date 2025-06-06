import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import MemoryStats from "../components/MemoryStats";

interface StatsData {
    success: boolean;
    total_memories: number;
    domain_distribution: Record<string, number>;
    top_tags: Record<string, number>;
    vector_collection_info?: {
        points_count: number;
        vectors_count?: number;
        status?: string;
    };
}

const MemoryStatsPage: React.FC = () => {
    const [stats, setStats] = useState<StatsData | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [userId, setUserId] = useState<string>("");
    const [fetchingStats, setFetchingStats] = useState<boolean>(false);
    const [searchParams] = useSearchParams();

    // Function to fetch stats
    const fetchStats = async (userIdToFetch: string) => {
        if (!userIdToFetch.trim()) {
            setError("Please enter a valid User ID");
            return;
        }

        setFetchingStats(true);
        setError(null);

        try {
            const response = await fetch(
                `/api/memories/stats/?user_id=${encodeURIComponent(
                    userIdToFetch
                )}`
            );

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(
                    errorData.error || "Failed to fetch statistics"
                );
            }

            const data: StatsData = await response.json();
            setStats(data);
        } catch (err) {
            console.error("Error fetching stats:", err);
            setError(
                err instanceof Error
                    ? err.message
                    : "Failed to fetch statistics"
            );
            setStats(null);
        } finally {
            setFetchingStats(false);
        }
    };

    // Handle form submission
    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        fetchStats(userId);
    };

    // Load default stats on component mount (optional - you might want to remove this)
    useEffect(() => {
        setLoading(false);
    }, []);

    // Initialize userId from URL params
    useEffect(() => {
        const userIdFromUrl = searchParams.get("user_id") || "";
        setUserId(userIdFromUrl);
        if (userIdFromUrl) {
            setLoading(true);
            fetchStats(userIdFromUrl);
            setLoading(false);
        }
    }, [searchParams]);

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Header */}
            <header className="bg-white shadow-sm">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center py-6">
                        <div className="flex items-center">
                            <h1 className="text-3xl font-bold text-gray-900">
                                Memory Statistics
                            </h1>
                            <span className="ml-3 text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                                Analytics
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
                {/* User ID Input Section */}
                <div className="bg-white rounded-lg shadow-md p-6 mb-8">
                    <div className="mb-6">
                        <h2 className="text-xl font-semibold text-gray-900 mb-2">
                            View Memory Statistics
                        </h2>
                        <p className="text-gray-600">
                            Enter a User ID to view detailed memory statistics
                            and analytics.
                        </p>
                    </div>

                    <form
                        onSubmit={handleSubmit}
                        className="flex gap-4 items-end"
                    >
                        <div className="flex-1">
                            <label
                                htmlFor="userId"
                                className="block text-sm font-medium text-gray-700 mb-2"
                            >
                                User ID
                            </label>
                            <input
                                type="text"
                                id="userId"
                                value={userId}
                                onChange={(e) => setUserId(e.target.value)}
                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                placeholder="e.g., 550e8400-e29b-41d4-a716-446655440000"
                                required
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={fetchingStats}
                            className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200"
                        >
                            {fetchingStats ? (
                                <div className="flex items-center">
                                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                                    Loading...
                                </div>
                            ) : (
                                "Get Statistics"
                            )}
                        </button>
                    </form>
                </div>

                {/* Error Display */}
                {error && (
                    <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-8">
                        <div className="flex">
                            <div className="flex-shrink-0">
                                <svg
                                    className="h-5 w-5 text-red-400"
                                    viewBox="0 0 20 20"
                                    fill="currentColor"
                                >
                                    <path
                                        fillRule="evenodd"
                                        d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                                        clipRule="evenodd"
                                    />
                                </svg>
                            </div>
                            <div className="ml-3">
                                <h3 className="text-sm font-medium text-red-800">
                                    Error
                                </h3>
                                <p className="text-sm text-red-700 mt-1">
                                    {error}
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Stats Display */}
                {stats && (
                    <div className="space-y-8">
                        {/* Main Stats Card */}
                        <MemoryStats stats={stats} />

                        {/* Additional Analytics */}
                        <div className="grid md:grid-cols-2 gap-6">
                            {/* Vector Database Info */}
                            {stats.vector_collection_info && (
                                <div className="bg-white rounded-lg shadow p-6">
                                    <h3 className="text-lg font-semibold text-gray-900 mb-4">
                                        Vector Database Status
                                    </h3>
                                    <div className="space-y-3">
                                        <div className="flex justify-between items-center">
                                            <span className="text-sm text-gray-600">
                                                Total Vectors:
                                            </span>
                                            <span className="font-medium text-gray-900">
                                                {stats.vector_collection_info.points_count?.toLocaleString() ||
                                                    "N/A"}
                                            </span>
                                        </div>
                                        <div className="flex justify-between items-center">
                                            <span className="text-sm text-gray-600">
                                                Status:
                                            </span>
                                            <span
                                                className={`px-2 py-1 rounded-full text-xs font-medium ${
                                                    stats.vector_collection_info
                                                        .status === "green"
                                                        ? "bg-green-100 text-green-800"
                                                        : "bg-yellow-100 text-yellow-800"
                                                }`}
                                            >
                                                {stats.vector_collection_info
                                                    .status || "Unknown"}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Quick Actions */}
                            <div className="bg-white rounded-lg shadow p-6">
                                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                                    Quick Actions
                                </h3>
                                <div className="space-y-3">
                                    <Link
                                        to={`/memories?user_id=${userId}`}
                                        className="block w-full px-4 py-2 bg-blue-600 text-white text-center rounded-md hover:bg-blue-700 transition-colors duration-200"
                                    >
                                        View All Memories
                                    </Link>
                                    <Link
                                        to="/devtools"
                                        className="block w-full px-4 py-2 bg-purple-600 text-white text-center rounded-md hover:bg-purple-700 transition-colors duration-200"
                                    >
                                        Test Memory Functions
                                    </Link>
                                    <Link
                                        to="/settings"
                                        className="block w-full px-4 py-2 bg-gray-600 text-white text-center rounded-md hover:bg-gray-700 transition-colors duration-200"
                                    >
                                        Configure Settings
                                    </Link>
                                </div>
                            </div>
                        </div>

                        {/* User Summary */}
                        <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-6 border border-blue-200">
                            <h3 className="text-lg font-semibold text-gray-900 mb-3">
                                User Memory Summary
                            </h3>
                            <div className="grid md:grid-cols-3 gap-4 text-sm">
                                <div>
                                    <span className="text-gray-600">
                                        User ID:
                                    </span>
                                    <p className="font-mono text-gray-900 break-all">
                                        {userId}
                                    </p>
                                </div>
                                <div>
                                    <span className="text-gray-600">
                                        Total Memories:
                                    </span>
                                    <p className="font-semibold text-blue-600">
                                        {stats.total_memories}
                                    </p>
                                </div>
                                <div>
                                    <span className="text-gray-600">
                                        Unique Tags:
                                    </span>
                                    <p className="font-semibold text-purple-600">
                                        {Object.keys(stats.top_tags).length}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* No Data State */}
                {!loading && !stats && !error && (
                    <div className="text-center py-12">
                        <svg
                            className="mx-auto h-12 w-12 text-gray-400"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                            />
                        </svg>
                        <h3 className="mt-4 text-lg font-medium text-gray-900">
                            No Statistics Loaded
                        </h3>
                        <p className="mt-2 text-gray-600">
                            Enter a User ID above to view memory statistics and
                            analytics.
                        </p>
                    </div>
                )}
            </main>
        </div>
    );
};

export default MemoryStatsPage;
