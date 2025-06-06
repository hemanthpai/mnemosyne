import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import MemoryList from "../components/MemoryList";
import { deleteAllMemories, listAllMemories } from "../services/api";
import { Memory } from "../types";

const MemoriesPage: React.FC = () => {
    const [memories, setMemories] = useState<Memory[]>([]);
    const [userId, setUserId] = useState<string>("");
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [deleting, setDeleting] = useState<boolean>(false);
    const [searchParams, setSearchParams] = useSearchParams();

    // Initialize userId from URL params
    useEffect(() => {
        const userIdFromUrl = searchParams.get("user_id") || "";
        setUserId(userIdFromUrl);
    }, [searchParams]);

    const handleDeleteAll = async () => {
        const targetUserId = userId.trim() || undefined;
        const confirmMessage = targetUserId
            ? `Are you sure you want to delete ALL memories for user ${targetUserId}? This action cannot be undone.`
            : "Are you sure you want to delete ALL memories for ALL users? This action cannot be undone.";

        if (!window.confirm(confirmMessage)) {
            return;
        }

        // Double confirmation for deleting all users' memories
        if (!targetUserId) {
            if (
                !window.confirm(
                    "FINAL WARNING: This will delete EVERYTHING from the database and vector storage. Type 'DELETE ALL' in the prompt that follows."
                )
            ) {
                return;
            }

            const confirmation = window.prompt("Type 'DELETE ALL' to confirm:");
            if (confirmation !== "DELETE ALL") {
                alert("Deletion cancelled - confirmation text did not match.");
                return;
            }
        }

        setDeleting(true);
        setError(null);
        setSuccess(null);

        try {
            const result = await deleteAllMemories(targetUserId);

            if (result.success) {
                setSuccess(
                    result.message ||
                        `Successfully deleted ${result.deleted_count} memories`
                );
                // Refresh the memories list
                const fetchedMemories = await listAllMemories(targetUserId);
                setMemories(fetchedMemories);
            } else {
                setError(result.error || "Failed to delete memories");
            }
        } catch (err: any) {
            setError(err.message || "Failed to delete memories");
            console.error("Error deleting memories:", err);
        } finally {
            setDeleting(false);
            // Clear success message after 5 seconds
            setTimeout(() => setSuccess(null), 5000);
        }
    };

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
                        <div className="flex items-center space-x-3">
                            <button
                                onClick={handleDeleteAll}
                                disabled={deleting}
                                className="inline-flex items-center px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200"
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
                                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                                    />
                                </svg>
                                {deleting
                                    ? "Deleting..."
                                    : userId
                                    ? "Delete User Memories"
                                    : "Delete All Memories"}
                            </button>
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

                {success && (
                    <div className="bg-green-50 border border-green-200 rounded-md p-4 mb-4">
                        <p className="text-green-800">{success}</p>
                    </div>
                )}

                <MemoryList memories={memories} />
            </div>
        </div>
    );
};

export default MemoriesPage;
