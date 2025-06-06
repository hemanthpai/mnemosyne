import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import MemoryList from "../components/MemoryList";
import { listAllMemories } from "../services/api";
import { Memory } from "../types";

const MemoriesPage: React.FC = () => {
    const [memories, setMemories] = useState<Memory[]>([]);
    const [userId, setUserId] = useState<string>("");
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [searchParams, setSearchParams] = useSearchParams();

    // Initialize userId from URL params
    useEffect(() => {
        const userIdFromUrl = searchParams.get("user_id") || "";
        setUserId(userIdFromUrl);
    }, [searchParams]);

    const handleUserIdChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const newUserId = event.target.value;
        setUserId(newUserId);

        // Update URL params
        if (newUserId.trim()) {
            setSearchParams({ user_id: newUserId });
        } else {
            setSearchParams({});
        }
    };

    useEffect(() => {
        const handleFetchMemories = async () => {
            setLoading(true);
            setError(null);

            try {
                // Fetch all memories if no userId, or filtered memories if userId provided
                const fetchedMemories = await listAllMemories(
                    userId.trim() || undefined
                );
                setMemories(fetchedMemories);
            } catch (err) {
                setError("Failed to fetch memories");
                console.error("Error fetching memories:", err);
            } finally {
                setLoading(false);
            }
        };

        handleFetchMemories();
    }, [userId]);

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Header */}
            <header className="bg-white shadow-sm">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center py-6">
                        <div className="flex items-center">
                            <h1 className="text-3xl font-bold text-gray-900">
                                Memories
                            </h1>
                            <span className="ml-3 text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                                Management
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
                {/* Filter Section */}
                <div className="bg-white rounded-lg shadow-md p-6 mb-8">
                    <div className="mb-4">
                        <h2 className="text-xl font-semibold text-gray-900 mb-2">
                            Filter Memories
                        </h2>
                        <p className="text-gray-600">
                            Enter a User ID to view memories for a specific
                            user, or leave blank to view all memories.
                        </p>
                    </div>
                    <div className="max-w-md">
                        <label
                            htmlFor="userId"
                            className="block text-sm font-medium text-gray-700 mb-2"
                        >
                            User ID (optional)
                        </label>
                        <input
                            id="userId"
                            type="text"
                            placeholder="Enter User ID (UUID) or leave blank for all"
                            value={userId}
                            onChange={handleUserIdChange}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                    </div>
                </div>

                {/* Loading State */}
                {loading && (
                    <div className="text-center py-12">
                        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                        <p className="mt-2 text-gray-600">
                            Loading memories...
                        </p>
                    </div>
                )}

                {/* Error State */}
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

                {/* Memory List */}
                <MemoryList memories={memories} />
            </main>
        </div>
    );
};

export default MemoriesPage;
