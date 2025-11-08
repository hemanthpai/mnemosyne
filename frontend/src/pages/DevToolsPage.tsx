import React, { useState } from "react";
import { Link } from "react-router-dom";
import { storeConversationTurn, searchConversations } from "../services/api";
import { StoreConversationTurnResponse, SearchConversationsResponse } from "../types";
import LatencyBadge from "../components/LatencyBadge";
import ConversationTurnCard from "../components/ConversationTurnCard";

const DevToolsPage: React.FC = () => {
    // Sample data
    const SAMPLE_USER_ID = "550e8400-e29b-41d4-a716-446655440000";
    const SAMPLE_SESSION = "dev-session-" + Date.now();

    // Store Turn State
    const [userId, setUserId] = useState<string>(SAMPLE_USER_ID);
    const [sessionId, setSessionId] = useState<string>(SAMPLE_SESSION);
    const [userMessage, setUserMessage] = useState<string>("");
    const [assistantMessage, setAssistantMessage] = useState<string>("");
    const [storeLoading, setStoreLoading] = useState<boolean>(false);
    const [storeResult, setStoreResult] = useState<StoreConversationTurnResponse | null>(null);
    const [storeError, setStoreError] = useState<string | null>(null);

    // Search State
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [searchUserId, setSearchUserId] = useState<string>(SAMPLE_USER_ID);
    const [searchLimit, setSearchLimit] = useState<number>(10);
    const [searchThreshold, setSearchThreshold] = useState<number>(0.5);
    const [searchMode, setSearchMode] = useState<'fast' | 'deep'>('fast');  // Phase 3: Search mode
    const [searchLoading, setSearchLoading] = useState<boolean>(false);
    const [searchResult, setSearchResult] = useState<SearchConversationsResponse | null>(null);
    const [searchError, setSearchError] = useState<string | null>(null);

    // Sample conversations
    const SAMPLE_CONVERSATIONS = [
        {
            user: "I love hiking in the mountains",
            assistant: "That's wonderful! Mountains offer great views and exercise.",
        },
        {
            user: "I prefer reading sci-fi novels",
            assistant: "Science fiction is fascinating! Any favorite authors?",
        },
        {
            user: "I'm learning to play guitar",
            assistant: "That's great! Playing an instrument is very rewarding.",
        },
    ];

    const handleStoreTurn = async () => {
        if (!userMessage.trim() || !assistantMessage.trim()) {
            setStoreError("Both messages are required");
            return;
        }

        setStoreLoading(true);
        setStoreError(null);
        setStoreResult(null);

        try {
            const result = await storeConversationTurn(
                userId,
                sessionId,
                userMessage,
                assistantMessage
            );
            setStoreResult(result);
            // Clear messages after successful store
            setUserMessage("");
            setAssistantMessage("");
        } catch (err: any) {
            setStoreError(err.response?.data?.error || "Failed to store conversation turn");
        } finally {
            setStoreLoading(false);
        }
    };

    const handleSearch = async () => {
        if (!searchQuery.trim()) {
            setSearchError("Search query is required");
            return;
        }

        setSearchLoading(true);
        setSearchError(null);
        setSearchResult(null);

        try {
            const result = await searchConversations(
                searchQuery,
                searchUserId,
                searchLimit,
                searchThreshold,
                searchMode  // Phase 3: Pass search mode
            );
            setSearchResult(result);
        } catch (err: any) {
            setSearchError(err.response?.data?.error || "Failed to search conversations");
        } finally {
            setSearchLoading(false);
        }
    };

    const loadSample = (sample: { user: string; assistant: string }) => {
        setUserMessage(sample.user);
        setAssistantMessage(sample.assistant);
    };

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Header */}
            <header className="bg-white shadow-sm">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center py-6">
                        <div className="flex items-center">
                            <h1 className="text-3xl font-bold text-gray-900">
                                Dev Tools
                            </h1>
                            <span className="ml-3 text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                                Phase 3
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
                <p className="text-gray-600 mb-6">
                    Test conversation storage and search with latency visualization
                </p>

            {/* Quick Test Data */}
            <div
                style={{
                    backgroundColor: "#f5f5f5",
                    padding: "16px",
                    borderRadius: "8px",
                    marginBottom: "24px",
                }}
            >
                <h3 style={{ marginTop: 0, marginBottom: "12px" }}>
                    📦 Quick Test Data
                </h3>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    {SAMPLE_CONVERSATIONS.map((sample, idx) => (
                        <button
                            key={idx}
                            onClick={() => loadSample(sample)}
                            style={{
                                padding: "8px 16px",
                                backgroundColor: "#1976d2",
                                color: "white",
                                border: "none",
                                borderRadius: "4px",
                                cursor: "pointer",
                                fontSize: "14px",
                            }}
                        >
                            Sample {idx + 1}: {sample.user.substring(0, 30)}...
                        </button>
                    ))}
                </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
                {/* Store Conversation Turn */}
                <div
                    style={{
                        border: "1px solid #e0e0e0",
                        borderRadius: "8px",
                        padding: "20px",
                        backgroundColor: "#fff",
                    }}
                >
                    <h2 style={{ marginTop: 0 }}>💾 Store Conversation Turn</h2>

                    <div style={{ marginBottom: "12px" }}>
                        <label style={{ display: "block", marginBottom: "4px", fontSize: "14px" }}>
                            User ID:
                        </label>
                        <input
                            type="text"
                            value={userId}
                            onChange={(e) => setUserId(e.target.value)}
                            style={{
                                width: "100%",
                                padding: "8px",
                                fontSize: "14px",
                                borderRadius: "4px",
                                border: "1px solid #ccc",
                            }}
                        />
                    </div>

                    <div style={{ marginBottom: "12px" }}>
                        <label style={{ display: "block", marginBottom: "4px", fontSize: "14px" }}>
                            Session ID:
                        </label>
                        <input
                            type="text"
                            value={sessionId}
                            onChange={(e) => setSessionId(e.target.value)}
                            style={{
                                width: "100%",
                                padding: "8px",
                                fontSize: "14px",
                                borderRadius: "4px",
                                border: "1px solid #ccc",
                            }}
                        />
                    </div>

                    <div style={{ marginBottom: "12px" }}>
                        <label style={{ display: "block", marginBottom: "4px", fontSize: "14px" }}>
                            User Message:
                        </label>
                        <textarea
                            value={userMessage}
                            onChange={(e) => setUserMessage(e.target.value)}
                            rows={3}
                            style={{
                                width: "100%",
                                padding: "8px",
                                fontSize: "14px",
                                borderRadius: "4px",
                                border: "1px solid #ccc",
                                fontFamily: "inherit",
                            }}
                            placeholder="Enter user message..."
                        />
                    </div>

                    <div style={{ marginBottom: "16px" }}>
                        <label style={{ display: "block", marginBottom: "4px", fontSize: "14px" }}>
                            Assistant Message:
                        </label>
                        <textarea
                            value={assistantMessage}
                            onChange={(e) => setAssistantMessage(e.target.value)}
                            rows={3}
                            style={{
                                width: "100%",
                                padding: "8px",
                                fontSize: "14px",
                                borderRadius: "4px",
                                border: "1px solid #ccc",
                                fontFamily: "inherit",
                            }}
                            placeholder="Enter assistant response..."
                        />
                    </div>

                    <button
                        onClick={handleStoreTurn}
                        disabled={storeLoading}
                        style={{
                            width: "100%",
                            padding: "12px",
                            backgroundColor: storeLoading ? "#ccc" : "#4caf50",
                            color: "white",
                            border: "none",
                            borderRadius: "4px",
                            fontSize: "16px",
                            fontWeight: "600",
                            cursor: storeLoading ? "not-allowed" : "pointer",
                        }}
                    >
                        {storeLoading ? "Storing..." : "Store Turn"}
                    </button>

                    {storeError && (
                        <div
                            style={{
                                marginTop: "12px",
                                padding: "12px",
                                backgroundColor: "#ffebee",
                                border: "1px solid #ef5350",
                                borderRadius: "4px",
                                color: "#c62828",
                            }}
                        >
                            ❌ {storeError}
                        </div>
                    )}

                    {storeResult && (
                        <div
                            style={{
                                marginTop: "12px",
                                padding: "12px",
                                backgroundColor: "#e8f5e9",
                                border: "1px solid #66bb6a",
                                borderRadius: "4px",
                            }}
                        >
                            <div style={{ marginBottom: "8px" }}>
                                ✅ <strong>Success!</strong>
                            </div>
                            <div style={{ fontSize: "14px", marginBottom: "8px" }}>
                                Turn ID: {storeResult.turn_id}
                                <br />
                                Turn Number: #{storeResult.turn_number}
                            </div>
                            <LatencyBadge latencyMs={storeResult.latency_ms} targetMs={100} />
                        </div>
                    )}
                </div>

                {/* Search Conversations */}
                <div
                    style={{
                        border: "1px solid #e0e0e0",
                        borderRadius: "8px",
                        padding: "20px",
                        backgroundColor: "#fff",
                    }}
                >
                    <h2 style={{ marginTop: 0 }}>🔍 Search Conversations</h2>

                    <div style={{ marginBottom: "12px" }}>
                        <label style={{ display: "block", marginBottom: "4px", fontSize: "14px" }}>
                            Search Query:
                        </label>
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            style={{
                                width: "100%",
                                padding: "8px",
                                fontSize: "14px",
                                borderRadius: "4px",
                                border: "1px solid #ccc",
                            }}
                            placeholder="e.g., hiking, reading, music..."
                        />
                    </div>

                    <div style={{ marginBottom: "12px" }}>
                        <label style={{ display: "block", marginBottom: "4px", fontSize: "14px" }}>
                            User ID:
                        </label>
                        <input
                            type="text"
                            value={searchUserId}
                            onChange={(e) => setSearchUserId(e.target.value)}
                            style={{
                                width: "100%",
                                padding: "8px",
                                fontSize: "14px",
                                borderRadius: "4px",
                                border: "1px solid #ccc",
                            }}
                        />
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "16px" }}>
                        <div>
                            <label style={{ display: "block", marginBottom: "4px", fontSize: "14px" }}>
                                Limit: {searchLimit}
                            </label>
                            <input
                                type="range"
                                min="1"
                                max="50"
                                value={searchLimit}
                                onChange={(e) => setSearchLimit(Number(e.target.value))}
                                style={{ width: "100%" }}
                            />
                        </div>
                        <div>
                            <label style={{ display: "block", marginBottom: "4px", fontSize: "14px" }}>
                                Threshold: {searchThreshold.toFixed(2)}
                            </label>
                            <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.05"
                                value={searchThreshold}
                                onChange={(e) => setSearchThreshold(Number(e.target.value))}
                                style={{ width: "100%" }}
                            />
                        </div>
                    </div>

                    {/* Phase 3: Search Mode Toggle */}
                    <div style={{ marginBottom: "16px" }}>
                        <label style={{ display: "block", marginBottom: "8px", fontSize: "14px", fontWeight: "600" }}>
                            Search Mode:
                        </label>
                        <div style={{ display: "flex", gap: "8px" }}>
                            <button
                                onClick={() => setSearchMode('fast')}
                                style={{
                                    flex: 1,
                                    padding: "10px",
                                    backgroundColor: searchMode === 'fast' ? "#2196f3" : "#f5f5f5",
                                    color: searchMode === 'fast' ? "white" : "#333",
                                    border: searchMode === 'fast' ? "2px solid #1976d2" : "2px solid #e0e0e0",
                                    borderRadius: "4px",
                                    fontSize: "14px",
                                    fontWeight: "600",
                                    cursor: "pointer",
                                    transition: "all 0.2s"
                                }}
                            >
                                ⚡ Fast
                                <div style={{ fontSize: "11px", fontWeight: "normal", marginTop: "2px" }}>
                                    Cache + Conversations
                                </div>
                            </button>
                            <button
                                onClick={() => setSearchMode('deep')}
                                style={{
                                    flex: 1,
                                    padding: "10px",
                                    backgroundColor: searchMode === 'deep' ? "#9c27b0" : "#f5f5f5",
                                    color: searchMode === 'deep' ? "white" : "#333",
                                    border: searchMode === 'deep' ? "2px solid #7b1fa2" : "2px solid #e0e0e0",
                                    borderRadius: "4px",
                                    fontSize: "14px",
                                    fontWeight: "600",
                                    cursor: "pointer",
                                    transition: "all 0.2s"
                                }}
                            >
                                🧠 Deep
                                <div style={{ fontSize: "11px", fontWeight: "normal", marginTop: "2px" }}>
                                    + Atomic Notes + Graph
                                </div>
                            </button>
                        </div>
                    </div>

                    <button
                        onClick={handleSearch}
                        disabled={searchLoading}
                        style={{
                            width: "100%",
                            padding: "12px",
                            backgroundColor: searchLoading ? "#ccc" : "#2196f3",
                            color: "white",
                            border: "none",
                            borderRadius: "4px",
                            fontSize: "16px",
                            fontWeight: "600",
                            cursor: searchLoading ? "not-allowed" : "pointer",
                        }}
                    >
                        {searchLoading ? "Searching..." : "Search"}
                    </button>

                    {searchError && (
                        <div
                            style={{
                                marginTop: "12px",
                                padding: "12px",
                                backgroundColor: "#ffebee",
                                border: "1px solid #ef5350",
                                borderRadius: "4px",
                                color: "#c62828",
                            }}
                        >
                            ❌ {searchError}
                        </div>
                    )}

                    {searchResult && (
                        <div style={{ marginTop: "12px" }}>
                            <div style={{ marginBottom: "12px" }}>
                                <LatencyBadge latencyMs={searchResult.latency_ms} targetMs={300} label="Search" />
                                {/* Phase 3: Show mode indicator */}
                                {searchResult.mode && (
                                    <div style={{
                                        marginTop: "8px",
                                        padding: "6px 12px",
                                        backgroundColor: searchResult.mode === 'deep' ? "#f3e5f5" : "#e3f2fd",
                                        border: searchResult.mode === 'deep' ? "1px solid #9c27b0" : "1px solid #2196f3",
                                        borderRadius: "4px",
                                        fontSize: "12px",
                                        display: "inline-block"
                                    }}>
                                        {searchResult.mode === 'deep' ? '🧠 Deep Mode' : '⚡ Fast Mode'}
                                    </div>
                                )}
                                <div style={{ marginTop: "8px", fontSize: "14px", color: "#666" }}>
                                    Found {searchResult.count} result(s)
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Search Results */}
            {searchResult && searchResult.results.length > 0 && (
                <div style={{ marginTop: "24px" }}>
                    <h2>Search Results ({searchResult.count})</h2>
                    {searchResult.results.map((result) => {
                        // Phase 3: Check if this is an atomic note or a conversation
                        const isAtomicNote = result.content !== undefined;

                        if (isAtomicNote) {
                            // Render atomic note
                            return (
                                <div
                                    key={result.id}
                                    style={{
                                        border: "2px solid #9c27b0",
                                        borderRadius: "8px",
                                        padding: "16px",
                                        marginBottom: "16px",
                                        backgroundColor: "#fafafa"
                                    }}
                                >
                                    <div style={{ marginBottom: "12px", display: "flex", justifyContent: "space-between", alignItems: "start" }}>
                                        <div>
                                            <span style={{
                                                backgroundColor: "#9c27b0",
                                                color: "white",
                                                padding: "4px 8px",
                                                borderRadius: "4px",
                                                fontSize: "12px",
                                                fontWeight: "600",
                                                marginRight: "8px"
                                            }}>
                                                📝 Atomic Note
                                            </span>
                                            {result.source && (
                                                <span style={{
                                                    backgroundColor: result.source === 'graph_traversal' ? "#ff9800" : "#2196f3",
                                                    color: "white",
                                                    padding: "4px 8px",
                                                    borderRadius: "4px",
                                                    fontSize: "11px",
                                                    marginRight: "8px"
                                                }}>
                                                    {result.source === 'graph_traversal' ? '🔗 Graph' : '🎯 Direct'}
                                                </span>
                                            )}
                                            <span style={{
                                                backgroundColor: "#e0e0e0",
                                                padding: "4px 8px",
                                                borderRadius: "4px",
                                                fontSize: "11px",
                                                color: "#666"
                                            }}>
                                                {result.note_type}
                                            </span>
                                        </div>
                                        <div style={{ textAlign: "right" }}>
                                            {result.score !== undefined && (
                                                <div style={{
                                                    fontSize: "12px",
                                                    color: "#666",
                                                    marginBottom: "4px"
                                                }}>
                                                    Score: {result.score.toFixed(3)}
                                                </div>
                                            )}
                                            {result.confidence !== undefined && (
                                                <div style={{
                                                    fontSize: "11px",
                                                    color: "#666"
                                                }}>
                                                    Confidence: {result.confidence.toFixed(2)}
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    <div style={{
                                        fontSize: "16px",
                                        fontWeight: "500",
                                        marginBottom: "8px",
                                        color: "#333"
                                    }}>
                                        {result.content}
                                    </div>

                                    {result.context && (
                                        <div style={{
                                            fontSize: "13px",
                                            color: "#666",
                                            fontStyle: "italic",
                                            marginBottom: "8px"
                                        }}>
                                            Context: {result.context}
                                        </div>
                                    )}

                                    {result.tags && result.tags.length > 0 && (
                                        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "8px" }}>
                                            {result.tags.map((tag, idx) => (
                                                <span
                                                    key={idx}
                                                    style={{
                                                        backgroundColor: "#e8eaf6",
                                                        color: "#3f51b5",
                                                        padding: "2px 8px",
                                                        borderRadius: "12px",
                                                        fontSize: "11px"
                                                    }}
                                                >
                                                    #{tag}
                                                </span>
                                            ))}
                                        </div>
                                    )}

                                    {result.depth !== undefined && result.depth > 0 && (
                                        <div style={{
                                            fontSize: "11px",
                                            color: "#ff9800",
                                            marginTop: "8px",
                                            fontWeight: "600"
                                        }}>
                                            🔗 Found via {result.relationship_type} relationship (depth: {result.depth})
                                        </div>
                                    )}
                                </div>
                            );
                        } else {
                            // Render conversation turn
                            return (
                                <div key={result.id}>
                                    <ConversationTurnCard
                                        turn={{
                                            id: result.id,
                                            user_id: searchUserId,
                                            session_id: result.session_id || "",
                                            turn_number: result.turn_number || 0,
                                            user_message: result.user_message || "",
                                            assistant_message: result.assistant_message || "",
                                            timestamp: result.timestamp || "",
                                            vector_id: "",
                                            extracted: false,
                                        }}
                                        score={result.score}
                                        highlight={searchQuery}
                                    />
                                    {/* Phase 3: Show source indicator for multi-tier search */}
                                    {result.source && (
                                        <div style={{
                                            fontSize: "11px",
                                            color: "#666",
                                            marginTop: "-12px",
                                            marginBottom: "12px",
                                            paddingLeft: "16px"
                                        }}>
                                            Source: {result.source === 'working_memory' ? '💾 Cache' : '🔍 Vector Search'}
                                        </div>
                                    )}
                                </div>
                            );
                        }
                    })}
                </div>
            )}
            </main>
        </div>
    );
};

export default DevToolsPage;
