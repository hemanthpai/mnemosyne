import React, { useState } from "react";
import { Link } from "react-router-dom";
import { extractMemories, retrieveMemories } from "../services/api";
import { ExtractMemoriesResponse, RetrieveMemoriesResponse } from "../types";

const DevToolsPage: React.FC = () => {
    // Extraction state
    const [extractionText, setExtractionText] = useState<string>("");
    const [extractionUserId, setExtractionUserId] = useState<string>("");
    const [extractionLoading, setExtractionLoading] = useState<boolean>(false);
    const [extractionResult, setExtractionResult] = useState<ExtractMemoriesResponse | null>(null);
    const [extractionError, setExtractionError] = useState<string | null>(null);

    // Retrieval state
    const [retrievalPrompt, setRetrievalPrompt] = useState<string>("");
    const [retrievalUserId, setRetrievalUserId] = useState<string>("");
    const [retrievalLoading, setRetrievalLoading] = useState<boolean>(false);
    const [retrievalResult, setRetrievalResult] = useState<RetrieveMemoriesResponse | null>(null);
    const [retrievalError, setRetrievalError] = useState<string | null>(null);

    const handleExtractMemories = async () => {
        if (!extractionText.trim() || !extractionUserId.trim()) {
            setExtractionError("Both conversation text and user ID are required");
            return;
        }

        setExtractionLoading(true);
        setExtractionError(null);
        setExtractionResult(null);

        try {
            const result = await extractMemories(extractionText, extractionUserId);
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
            const result = await retrieveMemories(retrievalPrompt, retrievalUserId);
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
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Header */}
                <div className="mb-8">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-3xl font-bold text-gray-900 mb-2">DevTools</h1>
                            <p className="text-gray-600">Test memory extraction and retrieval functionality</p>
                        </div>
                        <div className="flex space-x-4">
                            <button
                                onClick={loadSampleData}
                                className="inline-flex items-center px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition-colors duration-200"
                            >
                                <svg className="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                </svg>
                                Load Sample Data
                            </button>
                            <Link
                                to="/"
                                className="inline-flex items-center px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors duration-200"
                            >
                                <svg className="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                                </svg>
                                Back to Home
                            </Link>
                        </div>
                    </div>
                </div>

                <div className="grid lg:grid-cols-2 gap-8">
                    {/* Memory Extraction Section */}
                    <div className="bg-white rounded-lg shadow-md">
                        <div className="px-6 py-4 border-b border-gray-200">
                            <div className="flex items-center justify-between">
                                <h2 className="text-xl font-bold text-gray-900">Memory Extraction</h2>
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
                                    onChange={(e) => setExtractionUserId(e.target.value)}
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
                                    onChange={(e) => setExtractionText(e.target.value)}
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
                                {extractionLoading ? "Extracting..." : "Extract Memories"}
                            </button>

                            {/* Extraction Results */}
                            {extractionError && (
                                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                                    <p className="text-red-800">{extractionError}</p>
                                </div>
                            )}

                            {extractionResult && (
                                <div className="bg-green-50 border border-green-200 rounded-md p-4">
                                    <h3 className="font-medium text-green-800 mb-2">Extraction Result:</h3>
                                    <div className="text-sm text-green-700">
                                        <p><strong>Success:</strong> {extractionResult.success ? "Yes" : "No"}</p>
                                        <p><strong>Memories Extracted:</strong> {extractionResult.memories_extracted}</p>
                                        <p><strong>Message:</strong> {extractionResult.message}</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Memory Retrieval Section */}
                    <div className="bg-white rounded-lg shadow-md">
                        <div className="px-6 py-4 border-b border-gray-200">
                            <div className="flex items-center justify-between">
                                <h2 className="text-xl font-bold text-gray-900">Memory Retrieval</h2>
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
                                    onChange={(e) => setRetrievalUserId(e.target.value)}
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
                                    onChange={(e) => setRetrievalPrompt(e.target.value)}
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
                                {retrievalLoading ? "Retrieving..." : "Retrieve Memories"}
                            </button>

                            {/* Retrieval Results */}
                            {retrievalError && (
                                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                                    <p className="text-red-800">{retrievalError}</p>
                                </div>
                            )}

                            {retrievalResult && (
                                <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
                                    <h3 className="font-medium text-blue-800 mb-2">Retrieval Result:</h3>
                                    <div className="text-sm text-blue-700 space-y-2">
                                        <p><strong>Success:</strong> {retrievalResult.success ? "Yes" : "No"}</p>
                                        <p><strong>Memories Found:</strong> {retrievalResult.memories?.length || 0}</p>
                                        <p><strong>Message:</strong> {retrievalResult.message}</p>
                                        
                                        {retrievalResult.memories && retrievalResult.memories.length > 0 && (
                                            <div className="mt-3">
                                                <p className="font-medium mb-2">Retrieved Memories:</p>
                                                <div className="space-y-2">
                                                    {retrievalResult.memories.map((memory, index) => (
                                                        <div key={memory.id || index} className="bg-white p-3 rounded border">
                                                            <p className="text-sm text-gray-800">{memory.content}</p>
                                                            <p className="text-xs text-gray-500 mt-1">
                                                                Created: {new Date(memory.created_at).toLocaleString()}
                                                            </p>
                                                        </div>
                                                    ))}
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
                    <h3 className="text-lg font-medium text-gray-900 mb-4">API Status & Tips</h3>
                    <div className="grid md:grid-cols-2 gap-6">
                        <div>
                            <h4 className="font-medium text-gray-700 mb-2">Memory Extraction</h4>
                            <ul className="text-sm text-gray-600 space-y-1">
                                <li>• Extracts important information from conversations</li>
                                <li>• Currently returns stub data (not implemented)</li>
                                <li>• Will use LLM to identify memorable content</li>
                                <li>• Stores extracted memories with embeddings</li>
                            </ul>
                        </div>
                        <div>
                            <h4 className="font-medium text-gray-700 mb-2">Memory Retrieval</h4>
                            <ul className="text-sm text-gray-600 space-y-1">
                                <li>• Finds relevant memories based on prompts</li>
                                <li>• Currently returns stub data (not implemented)</li>
                                <li>• Will use semantic search with embeddings</li>
                                <li>• Returns ranked list of relevant memories</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default DevToolsPage;