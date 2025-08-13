import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { extractMemories, retrieveMemories } from "../services/api";
import {
    ExtractMemoriesResponse,
    RetrieveMemoriesResponse,
} from "../types/index";

const DevToolsPage: React.FC = () => {
    // Extraction state
    const [extractionText, setExtractionText] = useState<string>("");
    const [extractionUserId, setExtractionUserId] = useState<string>("");
    const [extractionLoading, setExtractionLoading] = useState<boolean>(false);
    const [extractionResult, setExtractionResult] =
        useState<ExtractMemoriesResponse | null>(null);
    const [extractionError, setExtractionError] = useState<string | null>(null);

    // Retrieval state
    const [retrievalPrompt, setRetrievalPrompt] = useState<string>("");
    const [retrievalUserId, setRetrievalUserId] = useState<string>("");
    const [retrievalLoading, setRetrievalLoading] = useState<boolean>(false);
    const [retrievalResult, setRetrievalResult] =
        useState<RetrieveMemoriesResponse | null>(null);
    const [retrievalError, setRetrievalError] = useState<string | null>(null);
    const [searchParams] = useSearchParams();

    useEffect(() => {
        // Load initial data from search params if available
        const initialExtractionText = searchParams.get("extractionText") || "";
        const initialExtractionUserId =
            searchParams.get("extractionUserId") || "";
        const initialRetrievalPrompt =
            searchParams.get("retrievalPrompt") || "";
        const initialRetrievalUserId =
            searchParams.get("retrievalUserId") || "";

        setExtractionText(initialExtractionText);
        setExtractionUserId(initialExtractionUserId);
        setRetrievalPrompt(initialRetrievalPrompt);
        setRetrievalUserId(initialRetrievalUserId);
    }, [searchParams]);

    const handleExtractMemories = async () => {
        if (!extractionText.trim() || !extractionUserId.trim()) {
            setExtractionError(
                "Both conversation text and user ID are required"
            );
            return;
        }

        setExtractionLoading(true);
        setExtractionError(null);
        setExtractionResult(null);

        try {
            const result = await extractMemories(
                extractionText,
                extractionUserId
            );
            setExtractionResult(result);
        } catch (err) {
            setExtractionError("Failed to extract memories");
            console.error("Error extracting memories:", err);
        } finally {
            setExtractionLoading(false);
        }
    };

    const handleRetrieveMemories = async () => {
        if (!retrievalPrompt.trim() || !retrievalUserId.trim()) {
            setRetrievalError("Both prompt and user ID are required");
            return;
        }

        setRetrievalLoading(true);
        setRetrievalError(null);
        setRetrievalResult(null);

        try {
            const result = await retrieveMemories(
                retrievalPrompt,
                retrievalUserId
            );
            setRetrievalResult(result);
        } catch (err) {
            setRetrievalError("Failed to retrieve memories");
            console.error("Error retrieving memories:", err);
        } finally {
            setRetrievalLoading(false);
        }
    };

    const clearExtractionForm = () => {
        setExtractionText("");
        setExtractionUserId("");
        setExtractionResult(null);
        setExtractionError(null);
    };

    const clearRetrievalForm = () => {
        setRetrievalPrompt("");
        setRetrievalUserId("");
        setRetrievalResult(null);
        setRetrievalError(null);
    };

    const loadSampleData = () => {
        setExtractionText(`User: I really love dark themes in applications, they're easier on my eyes.
Assistant: I understand you prefer dark themes. Would you like me to help you enable dark mode in various applications?
User: Yes, that would be great! Also, I work primarily with React and TypeScript projects.
Assistant: Perfect! I'll remember that you prefer dark themes and work with React/TypeScript. Let me show you how to enable dark mode in VS Code and other development tools.
User: Thanks! By the way, my name is Alex and I'm based in San Francisco.`);
        setExtractionUserId("550e8400-e29b-41d4-a716-446655440000");

        setRetrievalPrompt("What do you know about this user's preferences?");
        setRetrievalUserId("550e8400-e29b-41d4-a716-446655440000");
    };

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Header */}
            <header className="bg-white shadow-sm">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center py-6">
                        <div className="flex items-center">
                            <h1 className="text-3xl font-bold text-gray-900">
                                DevTools
                            </h1>
                            <span className="ml-3 text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                                Testing
                            </span>
                        </div>
                        <div className="flex space-x-3">
                            <button
                                onClick={loadSampleData}
                                className="inline-flex items-center px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition-colors duration-200"
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
                                        d="M13 10V3L4 14h7v7l9-11h-7z"
                                    />
                                </svg>
                                Load Sample Data
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
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Description Section */}
                <div className="bg-white rounded-lg shadow-md p-6 mb-8">
                    <h2 className="text-xl font-semibold text-gray-900 mb-2">
                        Memory Testing Tools
                    </h2>
                    <p className="text-gray-600">
                        Test memory extraction and retrieval functionality with
                        real data. Use the sample data or enter your own to see
                        how the system processes and retrieves memories.
                    </p>
                </div>

                <div className="grid lg:grid-cols-2 gap-8">
                    {/* Memory Extraction Section */}
                    <div className="bg-white rounded-lg shadow-md">
                        <div className="px-6 py-4 border-b border-gray-200">
                            <div className="flex items-center justify-between">
                                <h2 className="text-xl font-bold text-gray-900">
                                    Memory Extraction
                                </h2>
                                <button
                                    onClick={clearExtractionForm}
                                    className="text-sm text-gray-500 hover:text-gray-700"
                                >
                                    Clear
                                </button>
                            </div>
                            <p className="text-sm text-gray-600 mt-1">
                                Extract memories from conversation text
                            </p>
                        </div>

                        <div className="p-6 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    User ID
                                </label>
                                <input
                                    type="text"
                                    value={extractionUserId}
                                    onChange={(e) =>
                                        setExtractionUserId(e.target.value)
                                    }
                                    placeholder="Enter UUID for the user"
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Conversation Text
                                </label>
                                <textarea
                                    value={extractionText}
                                    onChange={(e) =>
                                        setExtractionText(e.target.value)
                                    }
                                    placeholder="Enter conversation text to extract memories from..."
                                    rows={8}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>

                            <button
                                onClick={handleExtractMemories}
                                disabled={extractionLoading}
                                className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {extractionLoading
                                    ? "Extracting..."
                                    : "Extract Memories"}
                            </button>

                            {/* Extraction Results */}
                            {extractionError && (
                                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                                    <p className="text-red-800">
                                        {extractionError}
                                    </p>
                                </div>
                            )}

                            {extractionResult && (
                                <div className="bg-green-50 border border-green-200 rounded-md p-4">
                                    <h3 className="font-medium text-green-800 mb-2">
                                        Extraction Result:
                                    </h3>
                                    <div className="text-sm text-green-700">
                                        <p>
                                            <strong>Success:</strong>{" "}
                                            {extractionResult.success
                                                ? "Yes"
                                                : "No"}
                                        </p>
                                        <p>
                                            <strong>Memories Extracted:</strong>{" "}
                                            {
                                                extractionResult.memories_extracted
                                            }
                                        </p>
                                        {extractionResult.memories &&
                                            extractionResult.memories.length >
                                                0 && (
                                                <div className="mt-3">
                                                    <p className="font-medium mb-2">
                                                        Retrieved Memories:
                                                    </p>
                                                    <div className="space-y-2">
                                                        {extractionResult.memories.map(
                                                            (memory, index) => (
                                                                <div
                                                                    key={
                                                                        memory.id ||
                                                                        index
                                                                    }
                                                                    className="bg-white p-3 rounded border"
                                                                >
                                                                    <p className="text-sm text-gray-800">
                                                                        {
                                                                            memory.content
                                                                        }
                                                                    </p>
                                                                </div>
                                                            )
                                                        )}
                                                    </div>
                                                </div>
                                            )}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Memory Retrieval Section */}
                    <div className="bg-white rounded-lg shadow-md">
                        <div className="px-6 py-4 border-b border-gray-200">
                            <div className="flex items-center justify-between">
                                <h2 className="text-xl font-bold text-gray-900">
                                    Memory Retrieval
                                </h2>
                                <button
                                    onClick={clearRetrievalForm}
                                    className="text-sm text-gray-500 hover:text-gray-700"
                                >
                                    Clear
                                </button>
                            </div>
                            <p className="text-sm text-gray-600 mt-1">
                                Retrieve relevant memories for a prompt
                            </p>
                        </div>

                        <div className="p-6 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    User ID
                                </label>
                                <input
                                    type="text"
                                    value={retrievalUserId}
                                    onChange={(e) =>
                                        setRetrievalUserId(e.target.value)
                                    }
                                    placeholder="Enter UUID for the user"
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Prompt
                                </label>
                                <textarea
                                    value={retrievalPrompt}
                                    onChange={(e) =>
                                        setRetrievalPrompt(e.target.value)
                                    }
                                    placeholder="Enter a prompt to retrieve relevant memories..."
                                    rows={4}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>

                            <button
                                onClick={handleRetrieveMemories}
                                disabled={retrievalLoading}
                                className="w-full px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {retrievalLoading
                                    ? "Retrieving..."
                                    : "Retrieve Memories"}
                            </button>

                            {/* Retrieval Results */}
                            {retrievalError && (
                                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                                    <p className="text-red-800">
                                        {retrievalError}
                                    </p>
                                </div>
                            )}

                            {retrievalResult && (
                                <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
                                    <h3 className="font-medium text-blue-800 mb-2">
                                        Retrieval Result:
                                    </h3>
                                    <div className="text-sm text-blue-700 space-y-2">
                                        <p>
                                            <strong>Success:</strong>{" "}
                                            {retrievalResult.success
                                                ? "Yes"
                                                : "No"}
                                        </p>
                                        <p>
                                            <strong>Memories Found:</strong>{" "}
                                            {retrievalResult.memories?.length ||
                                                0}
                                        </p>
                                        <p>
                                            <strong>Summary:</strong>{" "}
                                            {
                                                retrievalResult.memory_summary
                                                    ?.summary
                                            }
                                        </p>
                                        <p>
                                            <strong>Relevant Context:</strong>{" "}
                                            {
                                                retrievalResult.memory_summary
                                                    ?.relevant_context
                                            }
                                        </p>
                                        <p>
                                            <strong>
                                                Memory Usage Counts:
                                            </strong>
                                            <ul className="list-disc pl-5">
                                                <li>
                                                    Total Memories:{" "}
                                                    {
                                                        retrievalResult
                                                            .memory_summary
                                                            ?.memory_usage
                                                            .total_memories
                                                    }
                                                </li>
                                                <li>
                                                    Highly Relevant:{" "}
                                                    {
                                                        retrievalResult
                                                            .memory_summary
                                                            ?.memory_usage
                                                            .highly_relevant
                                                    }
                                                </li>
                                                <li>
                                                    Moderately Relevant:{" "}
                                                    {
                                                        retrievalResult
                                                            .memory_summary
                                                            ?.memory_usage
                                                            .moderately_relevant
                                                    }
                                                </li>
                                                <li>
                                                    Context Relevant:{" "}
                                                    {
                                                        retrievalResult
                                                            .memory_summary
                                                            ?.memory_usage
                                                            .context_relevant
                                                    }
                                                </li>
                                            </ul>
                                        </p>

                                        {retrievalResult.memories &&
                                            retrievalResult.memories.length >
                                                0 && (
                                                <div className="mt-3">
                                                    <div className="flex justify-between items-center mb-2">
                                                        <p className="font-medium">
                                                            Retrieved Memories:
                                                        </p>
                                                        <div className="text-xs text-gray-500">
                                                            <span className="mr-3">Score: <span className="bg-green-100 text-green-800 px-1 rounded">≥0.7</span> <span className="bg-yellow-100 text-yellow-800 px-1 rounded">≥0.5</span> <span className="bg-gray-100 text-gray-800 px-1 rounded">&lt;0.5</span></span>
                                                            <span>Type: <span className="bg-blue-100 text-blue-800 px-1 rounded">direct</span> <span className="bg-purple-100 text-purple-800 px-1 rounded">semantic</span> <span className="bg-orange-100 text-orange-800 px-1 rounded">exp.</span></span>
                                                        </div>
                                                    </div>
                                                    <div className="space-y-2">
                                                        {retrievalResult.memories.map(
                                                            (memory, index) => (
                                                                <div
                                                                    key={
                                                                        memory.id ||
                                                                        index
                                                                    }
                                                                    className="bg-white p-3 rounded border"
                                                                >
                                                                    <div className="flex justify-between items-start mb-2">
                                                                        <p className="text-sm text-gray-800 flex-1">
                                                                            {
                                                                                memory.content
                                                                            }
                                                                        </p>
                                                                        {memory.search_metadata && (
                                                                            <div className="ml-3 flex flex-col items-end space-y-1">
                                                                                <span className={`px-2 py-1 rounded text-xs font-medium ${
                                                                                    memory.search_metadata.search_score >= 0.7 
                                                                                        ? 'bg-green-100 text-green-800'
                                                                                        : memory.search_metadata.search_score >= 0.5
                                                                                        ? 'bg-yellow-100 text-yellow-800'
                                                                                        : 'bg-gray-100 text-gray-800'
                                                                                }`}>
                                                                                    Score: {memory.search_metadata.search_score}
                                                                                </span>
                                                                                <span className={`px-2 py-1 rounded text-xs font-medium ${
                                                                                    memory.search_metadata.search_type === 'direct' 
                                                                                        ? 'bg-blue-100 text-blue-800'
                                                                                        : memory.search_metadata.search_type === 'semantic'
                                                                                        ? 'bg-purple-100 text-purple-800'
                                                                                        : memory.search_metadata.search_type === 'experiential'
                                                                                        ? 'bg-orange-100 text-orange-800'
                                                                                        : 'bg-gray-100 text-gray-800'
                                                                                }`}>
                                                                                    {memory.search_metadata.search_type}
                                                                                </span>
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                    <div className="flex justify-between items-center text-xs text-gray-500">
                                                                        <span>
                                                                            Created:{" "}
                                                                            {new Date(
                                                                                memory.created_at
                                                                            ).toLocaleString()}
                                                                        </span>
                                                                        {memory.search_metadata && (
                                                                            <span className="text-gray-400">
                                                                                Original: {memory.search_metadata.original_score} | 
                                                                                Confidence: {memory.search_metadata.query_confidence}
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                    {memory.metadata?.tags && memory.metadata.tags.length > 0 && (
                                                                        <div className="mt-2 flex flex-wrap gap-1">
                                                                            {memory.metadata.tags.slice(0, 5).map((tag, tagIndex) => (
                                                                                <span
                                                                                    key={tagIndex}
                                                                                    className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded"
                                                                                >
                                                                                    {tag}
                                                                                </span>
                                                                            ))}
                                                                            {memory.metadata.tags.length > 5 && (
                                                                                <span className="px-2 py-1 bg-gray-100 text-gray-500 text-xs rounded">
                                                                                    +{memory.metadata.tags.length - 5} more
                                                                                </span>
                                                                            )}
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            )
                                                        )}
                                                    </div>
                                                </div>
                                            )}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* API Status Section */}
                <div className="mt-8 bg-white rounded-lg shadow-md p-6">
                    <h3 className="text-lg font-medium text-gray-900 mb-4">
                        API Status & Tips
                    </h3>
                    <div className="grid md:grid-cols-2 gap-6">
                        <div>
                            <h4 className="font-medium text-gray-700 mb-2">
                                Memory Extraction
                            </h4>
                            <ul className="text-sm text-gray-600 space-y-1">
                                <li>
                                    • Extracts important information from
                                    conversations
                                </li>
                                <li>
                                    • Uses the specified LLM to identify
                                    memorable content
                                </li>
                                <li>
                                    • Supports OpenAI, OpenAI-compatible (LM Studio), and Ollama endpoints
                                </li>
                                <li>
                                    • Stores extracted memories with embeddings
                                    for fast retrieval
                                </li>
                            </ul>
                        </div>
                        <div>
                            <h4 className="font-medium text-gray-700 mb-2">
                                Memory Retrieval
                            </h4>
                            <ul className="text-sm text-gray-600 space-y-1">
                                <li>
                                    • Finds relevant memories based on prompts
                                </li>
                                <li>
                                    • Uses semantic search with embeddings for
                                    speed and accuracy
                                </li>
                                <li>
                                    • Returns ranked list of relevant memories
                                    along with a summary and context
                                </li>
                                <li>
                                    • Displays search scores and types for debugging
                                </li>
                                <li>
                                    • Applies quality filtering (default threshold: 0.35)
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
};

export default DevToolsPage;
