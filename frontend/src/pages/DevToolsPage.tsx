import React, { useState } from "react";
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
                searchThreshold
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
        <div style={{ padding: "20px", maxWidth: "1200px", margin: "0 auto" }}>
            <h1 style={{ marginBottom: "8px" }}>Dev Tools</h1>
            <p style={{ color: "#666", marginBottom: "24px" }}>
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
                    {searchResult.results.map((result) => (
                        <ConversationTurnCard
                            key={result.id}
                            turn={{
                                id: result.id,
                                user_id: searchUserId,
                                session_id: result.session_id,
                                turn_number: result.turn_number,
                                user_message: result.user_message,
                                assistant_message: result.assistant_message,
                                timestamp: result.timestamp,
                                vector_id: "",
                                extracted: false,
                            }}
                            score={result.score}
                            highlight={searchQuery}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

export default DevToolsPage;
