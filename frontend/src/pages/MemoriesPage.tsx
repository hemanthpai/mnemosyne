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
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="mb-8">
                    <div className="flex items-center justify-between mb-4">
                        <h1 className="text-3xl font-bold text-gray-900">
                            Memories
                        </h1>
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
                    <div className="max-w-md">
                        <label
                            htmlFor="userId"
                            className="block text-sm font-medium text-gray-700 mb-2"
                        >
                            Filter by User ID (optional)
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

                {loading && (
                    <div className="text-center py-4">
                        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                        <p className="mt-2 text-gray-600">
                            Loading memories...
                        </p>
                    </div>
                )}

                {error && (
                    <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-4">
                        <p className="text-red-800">{error}</p>
                    </div>
                )}

                <MemoryList memories={memories} />
            </div>
        </div>
    );
};

export default MemoriesPage;
