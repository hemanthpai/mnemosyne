import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { deleteMemory, getMemory, updateMemory } from "../services/api";
import { Memory } from "../types/index";

const MemoryDetailPage: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const [memory, setMemory] = useState<Memory | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [isEditing, setIsEditing] = useState<boolean>(false);
    const [editedContent, setEditedContent] = useState<string>("");
    const [editedTags, setEditedTags] = useState<string>("");
    const [editedContext, setEditedContext] = useState<string>("");
    const [editedConnections, setEditedConnections] = useState<string>("");

    useEffect(() => {
        const fetchMemory = async () => {
            if (!id) return;

            try {
                const fetchedMemory = await getMemory(id);
                setMemory(fetchedMemory);
                setEditedContent(fetchedMemory.content);
                setEditedTags((fetchedMemory.metadata?.tags || []).join(", "));
                setEditedContext(fetchedMemory.metadata?.context || "");
                setEditedConnections(
                    (fetchedMemory.metadata?.connections || []).join(", ")
                );
            } catch (err) {
                setError("Failed to fetch memory");
                console.error("Error fetching memory:", err);
            } finally {
                setLoading(false);
            }
        };

        fetchMemory();
    }, [id]);

    const handleSave = async () => {
        if (!memory || !id) return;

        try {
            const updatedMetadata = {
                ...memory.metadata,
                tags: editedTags
                    .split(",")
                    .map((tag) => tag.trim())
                    .filter((tag) => tag.length > 0),
                context: editedContext.trim(),
                connections: editedConnections
                    .split(",")
                    .map((conn) => conn.trim())
                    .filter((conn) => conn.length > 0),
            };

            const updatedMemory = await updateMemory(
                id,
                {
                    content: editedContent,
                    metadata: updatedMetadata,
                },
                true
            );

            setMemory(updatedMemory);
            setIsEditing(false);
        } catch (err) {
            setError("Failed to update memory");
            console.error("Error updating memory:", err);
        }
    };

    const handleDelete = async () => {
        if (
            !id ||
            !confirm(
                "Are you sure you want to delete this memory? This action cannot be undone."
            )
        )
            return;

        try {
            await deleteMemory(id);
            navigate("/memories");
        } catch (err) {
            setError("Failed to delete memory");
            console.error("Error deleting memory:", err);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                    <p className="mt-2 text-gray-600">Loading memory...</p>
                </div>
            </div>
        );
    }

    if (error || !memory) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                    <div className="mb-4">
                        <svg
                            className="mx-auto h-12 w-12 text-red-400"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 15.5c-.77.833.192 2.5 1.732 2.5z"
                            />
                        </svg>
                    </div>
                    <h3 className="text-lg font-medium text-gray-900 mb-2">
                        Memory Not Found
                    </h3>
                    <p className="text-red-600 mb-4">
                        {error || "The requested memory could not be found"}
                    </p>
                    <button
                        onClick={() => navigate("/memories")}
                        className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors duration-200"
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
                        Back to Memories
                    </button>
                </div>
            </div>
        );
    }

    // Helper functions
    const getConfidenceColor = (confidence: number) => {
        if (confidence >= 0.8) return "text-green-600 bg-green-100";
        if (confidence >= 0.6) return "text-yellow-600 bg-yellow-100";
        return "text-red-600 bg-red-100";
    };

    const getDomainTags = (tags: string[]) => {
        const domainTags = ["personal", "professional", "academic", "creative"];
        return tags.filter((tag) => domainTags.includes(tag.toLowerCase()));
    };

    const getRegularTags = (tags: string[]) => {
        const domainTags = ["personal", "professional", "academic", "creative"];
        return tags.filter((tag) => !domainTags.includes(tag.toLowerCase()));
    };

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        return {
            full: date.toLocaleString(),
            relative: getRelativeTime(date),
        };
    };

    const getRelativeTime = (date: Date) => {
        const now = new Date();
        const diffInSeconds = Math.floor(
            (now.getTime() - date.getTime()) / 1000
        );

        if (diffInSeconds < 60) return "Just now";
        if (diffInSeconds < 3600)
            return `${Math.floor(diffInSeconds / 60)} minutes ago`;
        if (diffInSeconds < 86400)
            return `${Math.floor(diffInSeconds / 3600)} hours ago`;
        if (diffInSeconds < 2592000)
            return `${Math.floor(diffInSeconds / 86400)} days ago`;
        return date.toLocaleDateString();
    };

    const tags = memory.metadata?.tags || [];
    const domainTags = getDomainTags(tags);
    const regularTags = getRegularTags(tags);
    const confidence = memory.metadata?.confidence || 0;
    const context = memory.metadata?.context || "";
    const connections = memory.metadata?.connections || [];
    const createdDate = formatDate(memory.created_at);
    const updatedDate = formatDate(memory.updated_at);

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Header */}
            <header className="bg-white shadow-sm">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center py-6">
                        <div className="flex items-center">
                            <button
                                onClick={() => navigate("/memories")}
                                className="mr-4 p-2 text-gray-400 hover:text-gray-600 transition-colors duration-200"
                            >
                                <svg
                                    className="w-6 h-6"
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
                            </button>
                            <h1 className="text-3xl font-bold text-gray-900">
                                Memory Details
                            </h1>
                            <span className="ml-3 text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                                ID: {memory.id.slice(0, 8)}...
                            </span>
                        </div>
                        <div className="flex space-x-3">
                            {isEditing ? (
                                <>
                                    <button
                                        onClick={handleSave}
                                        className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors duration-200"
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
                                                d="M5 13l4 4L19 7"
                                            />
                                        </svg>
                                        Save Changes
                                    </button>
                                    <button
                                        onClick={() => setIsEditing(false)}
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
                                                d="M6 18L18 6M6 6l12 12"
                                            />
                                        </svg>
                                        Cancel
                                    </button>
                                </>
                            ) : (
                                <>
                                    <button
                                        onClick={() => setIsEditing(true)}
                                        className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors duration-200"
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
                                                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                                            />
                                        </svg>
                                        Edit Memory
                                    </button>
                                    <button
                                        onClick={handleDelete}
                                        className="inline-flex items-center px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors duration-200"
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
                                        Delete
                                    </button>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="grid lg:grid-cols-3 gap-8">
                    {/* Main Content Column */}
                    <div className="lg:col-span-2 space-y-6">
                        {/* Memory Content */}
                        <div className="bg-white rounded-lg shadow-md p-6">
                            <h2 className="text-xl font-semibold text-gray-900 mb-4">
                                Content
                            </h2>
                            {isEditing ? (
                                <textarea
                                    value={editedContent}
                                    onChange={(e) =>
                                        setEditedContent(e.target.value)
                                    }
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                    rows={8}
                                    placeholder="Enter memory content..."
                                />
                            ) : (
                                <div className="bg-gray-50 p-4 rounded-md border-l-4 border-blue-500">
                                    <p className="text-gray-900 leading-relaxed whitespace-pre-wrap">
                                        {memory.content}
                                    </p>
                                </div>
                            )}
                        </div>

                        {/* Context */}
                        {(context || isEditing) && (
                            <div className="bg-white rounded-lg shadow-md p-6">
                                <h2 className="text-xl font-semibold text-gray-900 mb-4">
                                    Context
                                </h2>
                                {isEditing ? (
                                    <textarea
                                        value={editedContext}
                                        onChange={(e) =>
                                            setEditedContext(e.target.value)
                                        }
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                        rows={3}
                                        placeholder="Describe the context where this memory was mentioned..."
                                    />
                                ) : (
                                    <div className="bg-amber-50 p-4 rounded-md border-l-4 border-amber-500">
                                        <p className="text-gray-900">
                                            {context}
                                        </p>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Tags */}
                        <div className="bg-white rounded-lg shadow-md p-6">
                            <h2 className="text-xl font-semibold text-gray-900 mb-4">
                                Tags
                            </h2>
                            {isEditing ? (
                                <div>
                                    <input
                                        type="text"
                                        value={editedTags}
                                        onChange={(e) =>
                                            setEditedTags(e.target.value)
                                        }
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                        placeholder="Enter tags separated by commas (e.g., music, personal, favorite)"
                                    />
                                    <p className="text-sm text-gray-500 mt-1">
                                        Separate tags with commas
                                    </p>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {domainTags.length > 0 && (
                                        <div>
                                            <h3 className="text-sm font-medium text-gray-600 mb-2">
                                                Domain Tags
                                            </h3>
                                            <div className="flex flex-wrap gap-2">
                                                {domainTags.map((tag) => (
                                                    <span
                                                        key={tag}
                                                        className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800"
                                                    >
                                                        {tag}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {regularTags.length > 0 && (
                                        <div>
                                            <h3 className="text-sm font-medium text-gray-600 mb-2">
                                                Content Tags
                                            </h3>
                                            <div className="flex flex-wrap gap-2">
                                                {regularTags.map((tag) => (
                                                    <span
                                                        key={tag}
                                                        className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800"
                                                    >
                                                        {tag}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {tags.length === 0 && (
                                        <p className="text-gray-500 text-sm">
                                            No tags assigned
                                        </p>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Connections */}
                        {(connections.length > 0 || isEditing) && (
                            <div className="bg-white rounded-lg shadow-md p-6">
                                <h2 className="text-xl font-semibold text-gray-900 mb-4">
                                    Related Topics
                                </h2>
                                {isEditing ? (
                                    <div>
                                        <input
                                            type="text"
                                            value={editedConnections}
                                            onChange={(e) =>
                                                setEditedConnections(
                                                    e.target.value
                                                )
                                            }
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                            placeholder="Enter related topics separated by commas"
                                        />
                                        <p className="text-sm text-gray-500 mt-1">
                                            Topics this memory relates to
                                        </p>
                                    </div>
                                ) : (
                                    <div className="flex flex-wrap gap-2">
                                        {connections.map(
                                            (connection, index) => (
                                                <span
                                                    key={index}
                                                    className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-purple-100 text-purple-800"
                                                >
                                                    {connection}
                                                </span>
                                            )
                                        )}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Sidebar */}
                    <div className="space-y-6">
                        {/* Memory Statistics */}
                        <div className="bg-white rounded-lg shadow-md p-6">
                            <h2 className="text-lg font-semibold text-gray-900 mb-4">
                                Memory Statistics
                            </h2>
                            <div className="space-y-4">
                                <div className="flex items-center justify-between">
                                    <span className="text-sm text-gray-600">
                                        Confidence
                                    </span>
                                    <span
                                        className={`px-2 py-1 rounded-full text-xs font-medium ${getConfidenceColor(
                                            confidence
                                        )}`}
                                    >
                                        {(confidence * 100).toFixed(0)}%
                                    </span>
                                </div>

                                <div className="flex items-center justify-between">
                                    <span className="text-sm text-gray-600">
                                        Total Tags
                                    </span>
                                    <span className="text-sm font-medium text-gray-900">
                                        {tags.length}
                                    </span>
                                </div>

                                <div className="flex items-center justify-between">
                                    <span className="text-sm text-gray-600">
                                        Related Topics
                                    </span>
                                    <span className="text-sm font-medium text-gray-900">
                                        {connections.length}
                                    </span>
                                </div>

                                <div className="flex items-center justify-between">
                                    <span className="text-sm text-gray-600">
                                        Content Length
                                    </span>
                                    <span className="text-sm font-medium text-gray-900">
                                        {memory.content.length} chars
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Memory Metadata */}
                        <div className="bg-white rounded-lg shadow-md p-6">
                            <h2 className="text-lg font-semibold text-gray-900 mb-4">
                                Metadata
                            </h2>
                            <div className="space-y-3">
                                <div>
                                    <dt className="text-sm font-medium text-gray-600">
                                        User ID
                                    </dt>
                                    <dd className="text-sm text-gray-900 font-mono break-all">
                                        {memory.user_id}
                                    </dd>
                                </div>

                                <div>
                                    <dt className="text-sm font-medium text-gray-600">
                                        Memory ID
                                    </dt>
                                    <dd className="text-sm text-gray-900 font-mono break-all">
                                        {memory.id}
                                    </dd>
                                </div>

                                <div>
                                    <dt className="text-sm font-medium text-gray-600">
                                        Created
                                    </dt>
                                    <dd
                                        className="text-sm text-gray-900"
                                        title={createdDate.full}
                                    >
                                        {createdDate.relative}
                                    </dd>
                                </div>

                                <div>
                                    <dt className="text-sm font-medium text-gray-600">
                                        Last Updated
                                    </dt>
                                    <dd
                                        className="text-sm text-gray-900"
                                        title={updatedDate.full}
                                    >
                                        {updatedDate.relative}
                                    </dd>
                                </div>

                                {memory.metadata?.extraction_source && (
                                    <div>
                                        <dt className="text-sm font-medium text-gray-600">
                                            Source
                                        </dt>
                                        <dd className="text-sm text-gray-900">
                                            {memory.metadata.extraction_source}
                                        </dd>
                                    </div>
                                )}

                                {memory.metadata?.model_used && (
                                    <div>
                                        <dt className="text-sm font-medium text-gray-600">
                                            Model Used
                                        </dt>
                                        <dd className="text-sm text-gray-900">
                                            {memory.metadata.model_used}
                                        </dd>
                                    </div>
                                )}
                                {memory.metadata?.connections && (
                                    <div>
                                        <dt className="text-sm font-medium text-gray-600">
                                            Connections
                                        </dt>
                                        <dd className="text-sm text-gray-900">
                                            {memory.metadata.connections.join(
                                                ", "
                                            )}
                                        </dd>
                                    </div>
                                )}
                                {memory.metadata?.context && (
                                    <div>
                                        <dt className="text-sm font-medium text-gray-600">
                                            Context
                                        </dt>
                                        <dd className="text-sm text-gray-900">
                                            {memory.metadata.context}
                                        </dd>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Quick Actions */}
                        <div className="bg-white rounded-lg shadow-md p-6">
                            <h2 className="text-lg font-semibold text-gray-900 mb-4">
                                Quick Actions
                            </h2>
                            <div className="space-y-3">
                                <button
                                    onClick={() =>
                                        navigate(
                                            `/memories?user_id=${memory.user_id}`
                                        )
                                    }
                                    className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors duration-200 text-sm"
                                >
                                    View User's Memories
                                </button>

                                <button
                                    onClick={() =>
                                        navigate(
                                            `/stats?user_id=${memory.user_id}`
                                        )
                                    }
                                    className="w-full px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition-colors duration-200 text-sm"
                                >
                                    View User Stats
                                </button>

                                <button
                                    onClick={() => {
                                        const searchTerms = tags
                                            .slice(0, 3)
                                            .join(" ");
                                        navigate(
                                            `/devtools?retrievalPrompt=${encodeURIComponent(
                                                searchTerms
                                            )}&retrievalUserId=${
                                                memory.user_id
                                            }`
                                        );
                                    }}
                                    className="w-full px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors duration-200 text-sm"
                                >
                                    Test Related Search
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
};

export default MemoryDetailPage;
