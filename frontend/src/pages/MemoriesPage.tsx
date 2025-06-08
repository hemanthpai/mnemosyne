import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import MemoryList from "../components/MemoryList";
import { deleteAllMemories, listAllMemories } from "../services/api";
import { Memory } from "../types/index";

const MemoriesPage: React.FC = () => {
    const [memories, setMemories] = useState<Memory[]>([]);
    const [userId, setUserId] = useState<string>("");
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [deleting, setDeleting] = useState<boolean>(false);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState<boolean>(false);
    const [deleteSuccess, setDeleteSuccess] = useState<string | null>(null);
    const [searchParams, setSearchParams] = useSearchParams();

    // Initialize userId from URL params
    useEffect(() => {
        const userIdFromUrl = searchParams.get("user_id") || "";
        setUserId(userIdFromUrl);
    }, [searchParams]);

    const handleUserIdChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const newUserId = event.target.value;
        setUserId(newUserId);

        // Clear any success messages when changing user
        setDeleteSuccess(null);

        // Update URL params
        if (newUserId.trim()) {
            setSearchParams({ user_id: newUserId });
        } else {
            setSearchParams({});
        }
    };

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

    useEffect(() => {
        handleFetchMemories();
    }, [userId]);

    const handleDeleteAllClick = () => {
        setShowDeleteConfirm(true);
    };

    const handleDeleteConfirm = async () => {
        setDeleting(true);
        setError(null);
        setDeleteSuccess(null);
        setShowDeleteConfirm(false);

        try {
            const result = await deleteAllMemories(userId.trim() || undefined);

            if (result.success) {
                setDeleteSuccess(
                    result.message ||
                        `Successfully deleted ${result.deleted_count} memories`
                );
                // Refresh the memories list
                await handleFetchMemories();
            } else {
                setError(result.error || "Failed to delete memories");
            }
        } catch (err: any) {
            setError(`Failed to delete memories: ${err.message}`);
            console.error("Error deleting memories:", err);
        } finally {
            setDeleting(false);
        }
    };

    const handleDeleteCancel = () => {
        setShowDeleteConfirm(false);
    };

    const getDeleteButtonText = () => {
        if (userId.trim()) {
            return `Delete All Memories for User`;
        }
        return "Delete All Memories";
    };

    const getDeleteConfirmText = () => {
        const memoryCount = memories.length;
        if (userId.trim()) {
            return `Are you sure you want to delete all ${memoryCount} memories for user "${userId}"? This action cannot be undone.`;
        }
        return `Are you sure you want to delete ALL ${memoryCount} memories from the system? This will affect all users and cannot be undone.`;
    };

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
                    <div className="flex flex-col sm:flex-row sm:items-end gap-4">
                        <div className="flex-1 max-w-md">
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

                        {/* Delete All Button */}
                        <div className="flex-shrink-0">
                            <button
                                onClick={handleDeleteAllClick}
                                disabled={
                                    deleting || loading || memories.length === 0
                                }
                                className="inline-flex items-center px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors duration-200"
                            >
                                {deleting ? (
                                    <>
                                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                                        Deleting...
                                    </>
                                ) : (
                                    <>
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
                                        {getDeleteButtonText()}
                                    </>
                                )}
                            </button>
                        </div>
                    </div>

                    {/* Memory count display */}
                    {!loading && (
                        <div className="mt-4 text-sm text-gray-600">
                            {memories.length === 0
                                ? "No memories found"
                                : `Showing ${memories.length} ${
                                      memories.length === 1
                                          ? "memory"
                                          : "memories"
                                  }${
                                      userId.trim()
                                          ? ` for user "${userId}"`
                                          : " total"
                                  }`}
                        </div>
                    )}
                </div>

                {/* Success Message */}
                {deleteSuccess && (
                    <div className="bg-green-50 border border-green-200 rounded-md p-4 mb-8">
                        <div className="flex">
                            <div className="flex-shrink-0">
                                <svg
                                    className="h-5 w-5 text-green-400"
                                    viewBox="0 0 20 20"
                                    fill="currentColor"
                                >
                                    <path
                                        fillRule="evenodd"
                                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                                        clipRule="evenodd"
                                    />
                                </svg>
                            </div>
                            <div className="ml-3">
                                <h3 className="text-sm font-medium text-green-800">
                                    Success
                                </h3>
                                <p className="text-sm text-green-700 mt-1">
                                    {deleteSuccess}
                                </p>
                            </div>
                        </div>
                    </div>
                )}

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

            {/* Delete Confirmation Modal */}
            {showDeleteConfirm && (
                <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
                    <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
                        <div className="mt-3 text-center">
                            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
                                <svg
                                    className="h-6 w-6 text-red-600"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.268 15.5c-.77.833.192 2.5 1.732 2.5z"
                                    />
                                </svg>
                            </div>
                            <h3 className="text-lg leading-6 font-medium text-gray-900 mt-4">
                                Confirm Deletion
                            </h3>
                            <div className="mt-2 px-7 py-3">
                                <p className="text-sm text-gray-500">
                                    {getDeleteConfirmText()}
                                </p>
                            </div>
                            <div className="items-center px-4 py-3">
                                <div className="flex gap-3 justify-center">
                                    <button
                                        onClick={handleDeleteCancel}
                                        className="px-4 py-2 bg-gray-500 text-white text-base font-medium rounded-md shadow-sm hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-300"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        onClick={handleDeleteConfirm}
                                        className="px-4 py-2 bg-red-600 text-white text-base font-medium rounded-md shadow-sm hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-300"
                                    >
                                        Delete All
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default MemoriesPage;
