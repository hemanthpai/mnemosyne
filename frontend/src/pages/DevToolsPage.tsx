import React, { useState, useEffect } from "react";
import { storeConversationTurn, searchConversations } from "../services/api";
import { StoreConversationTurnResponse, SearchConversationsResponse } from "../types";
import LatencyBadge from "../components/LatencyBadge";
import ConversationTurnCard from "../components/ConversationTurnCard";
import PageHeader from "../components/PageHeader";
import Dropdown from "../components/Dropdown";
import { useSidebar } from "../contexts/SidebarContext";

// Auto-detect API base URL
const getApiBaseUrl = (): string => {
  if (typeof window === 'undefined') {
    return 'http://localhost:8000';
  }
  return '';
};

const API_BASE_URL = getApiBaseUrl();

type TabType = 'store' | 'search';

const DevToolsPage: React.FC = () => {
    const { isSidebarOpen } = useSidebar();
    // Tab state
    const [activeTab, setActiveTab] = useState<TabType>('store');

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
    const [searchUserId, setSearchUserId] = useState<string>(sessionStorage.getItem('devtools_user_id') || '');
    const [searchLimit, setSearchLimit] = useState<number>(10);
    const [searchThreshold, setSearchThreshold] = useState<number>(0.5);
    const [searchMode, setSearchMode] = useState<'fast' | 'deep'>('fast');
    const [searchLoading, setSearchLoading] = useState<boolean>(false);
    const [searchResult, setSearchResult] = useState<SearchConversationsResponse | null>(null);
    const [searchError, setSearchError] = useState<string | null>(null);

    // User management for search
    const [availableUsers, setAvailableUsers] = useState<Array<{ id: string; name: string }>>([]);

    // Sample conversations
    const SAMPLE_CONVERSATIONS = [
        {
            label: "Sample 1: Hiking",
            user: "I love hiking in the mountains",
            assistant: "That's wonderful! Mountains offer great views and exercise.",
        },
        {
            label: "Sample 2: Reading",
            user: "I prefer reading sci-fi novels",
            assistant: "Science fiction is fascinating! Any favorite authors?",
        },
        {
            label: "Sample 3: Music",
            user: "I'm learning to play guitar",
            assistant: "That's great! Playing an instrument is very rewarding.",
        },
    ];

    // Fetch available users on mount
    useEffect(() => {
        const loadUsers = async () => {
            try {
                const response = await fetch(`${API_BASE_URL}/api/notes/users/`);
                const data = await response.json();

                if (data.success && data.users.length > 0) {
                    // Map users to format expected by dropdown
                    const users = data.users.map((u: { user_id: string; note_count: number }) => ({
                        id: u.user_id,
                        name: `User ${u.user_id.substring(0, 8)} (${u.note_count} notes)`
                    }));
                    setAvailableUsers(users);

                    // Set initial searchUserId if not already set
                    if (!searchUserId) {
                        const firstUserId = users[0].id;
                        setSearchUserId(firstUserId);
                        sessionStorage.setItem('devtools_user_id', firstUserId);
                    }
                }
            } catch (err) {
                console.error('Failed to load users:', err);
            }
        };

        loadUsers();
    }, []);

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
                searchMode
            );
            setSearchResult(result);
        } catch (err: any) {
            setSearchError(err.response?.data?.error || "Failed to search conversations");
        } finally {
            setSearchLoading(false);
        }
    };

    const loadSample = (sample: { label: string; user: string; assistant: string }) => {
        setUserMessage(sample.user);
        setAssistantMessage(sample.assistant);
    };

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
            <PageHeader
                title="Dev Tools"
                subtitle="Test conversation storage and search with latency visualization"
                badge={{ text: "Development", color: "gray" }}
            />

            <div className={`transition-all duration-300 ${isSidebarOpen ? 'ml-60' : 'ml-0'}`}>
            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Tabs */}
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md mb-6">
                    {/* Tab Navigation */}
                    <div className="border-b border-gray-200 dark:border-gray-700">
                        {/* Mobile: Dropdown */}
                        <div className="sm:hidden px-4 py-3">
                            <label htmlFor="devtools-tab-select" className="sr-only">
                                Select tool
                            </label>
                            <select
                                id="devtools-tab-select"
                                value={activeTab}
                                onChange={(e) => setActiveTab(e.target.value as TabType)}
                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 dark:text-gray-100 text-sm font-medium"
                            >
                                <option value="store">Store Conversations</option>
                                <option value="search">Search & Query</option>
                            </select>
                        </div>

                        {/* Desktop: Tab Buttons */}
                        <nav className="hidden sm:flex -mb-px">
                            <button
                                onClick={() => setActiveTab('store')}
                                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                                    activeTab === 'store'
                                        ? 'border-green-500 text-green-600 dark:text-green-400'
                                        : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
                                }`}
                            >
                                💾 Store Conversations
                            </button>
                            <button
                                onClick={() => setActiveTab('search')}
                                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                                    activeTab === 'search'
                                        ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                                        : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
                                }`}
                            >
                                🔍 Search & Query
                            </button>
                        </nav>
                    </div>

                    {/* Tab Content */}
                    <div className="p-4 sm:p-6">
                        {/* Store Tab */}
                        {activeTab === 'store' && (
                            <div className="space-y-6">
                                {/* Quick Test Data */}
                                <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-4">
                                    <div className="flex items-center gap-2">
                                        <label htmlFor="sample-select" className="text-sm text-gray-700 dark:text-gray-300 font-medium whitespace-nowrap">
                                            Quick test:
                                        </label>
                                        <select
                                            id="sample-select"
                                            onChange={(e) => {
                                                const idx = parseInt(e.target.value);
                                                if (idx >= 0) loadSample(SAMPLE_CONVERSATIONS[idx]);
                                            }}
                                            className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-600 dark:text-gray-100 text-sm"
                                            defaultValue="-1"
                                        >
                                            <option value="-1">Load a sample conversation...</option>
                                            {SAMPLE_CONVERSATIONS.map((sample, idx) => (
                                                <option key={idx} value={idx}>
                                                    {sample.label}
                                                </option>
                                            ))}
                                        </select>
                                    </div>
                                </div>

                                <div className="space-y-4">
                            <div>
                                <label htmlFor="store-userId" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    User ID
                                </label>
                                <input
                                    id="store-userId"
                                    type="text"
                                    value={userId}
                                    onChange={(e) => setUserId(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-mono"
                                />
                            </div>

                            <div>
                                <label htmlFor="store-sessionId" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Session ID
                                </label>
                                <input
                                    id="store-sessionId"
                                    type="text"
                                    value={sessionId}
                                    onChange={(e) => setSessionId(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-mono"
                                />
                            </div>

                            <div>
                                <label htmlFor="store-userMessage" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    User Message
                                </label>
                                <textarea
                                    id="store-userMessage"
                                    value={userMessage}
                                    onChange={(e) => setUserMessage(e.target.value)}
                                    rows={3}
                                    placeholder="Enter user message..."
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm resize-y"
                                />
                            </div>

                            <div>
                                <label htmlFor="store-assistantMessage" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Assistant Message
                                </label>
                                <textarea
                                    id="store-assistantMessage"
                                    value={assistantMessage}
                                    onChange={(e) => setAssistantMessage(e.target.value)}
                                    rows={3}
                                    placeholder="Enter assistant response..."
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm resize-y"
                                />
                            </div>

                            <button
                                onClick={handleStoreTurn}
                                disabled={storeLoading}
                                className="w-full px-4 py-3 bg-green-600 text-white font-semibold rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                                {storeLoading ? "Storing..." : "Store Turn"}
                            </button>

                            {storeError && (
                                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md p-3">
                                    <p className="text-red-800 dark:text-red-300 text-sm">❌ {storeError}</p>
                                </div>
                            )}

                            {storeResult && (
                                <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-md p-3">
                                    <div className="mb-2">
                                        <span className="text-green-800 dark:text-green-300 font-semibold">✅ Success!</span>
                                    </div>
                                    <div className="text-sm text-gray-700 dark:text-gray-300 mb-2 space-y-1">
                                        <div className="font-mono text-xs">
                                            Turn ID: <span className="text-gray-900 dark:text-gray-100">{storeResult.turn_id}</span>
                                        </div>
                                        <div>
                                            Turn Number: <span className="font-semibold">#{storeResult.turn_number}</span>
                                        </div>
                                    </div>
                                    <LatencyBadge latencyMs={storeResult.latency_ms} targetMs={100} />
                                </div>
                            )}
                                </div>
                            </div>
                        )}

                        {/* Search Tab */}
                        {activeTab === 'search' && (
                            <div className="space-y-6">
                                {/* User Selection */}
                                {availableUsers.length > 0 && (
                                    <div>
                                        <label htmlFor="search-user-select" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                            Select User to Search
                                        </label>
                                        <Dropdown
                                            id="search-user-select"
                                            value={searchUserId}
                                            options={availableUsers.map(user => ({ value: user.id, label: user.name }))}
                                            onChange={(newUserId) => {
                                                setSearchUserId(newUserId);
                                                sessionStorage.setItem('devtools_user_id', newUserId);
                                            }}
                                            className="text-sm"
                                        />
                                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                            Search conversations and notes for this user
                                        </p>
                                    </div>
                                )}

                                <div className="space-y-4">
                            <div>
                                <label htmlFor="search-query" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Search Query
                                </label>
                                <input
                                    id="search-query"
                                    type="text"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    placeholder="e.g., hiking, reading, music..."
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                                />
                            </div>

                            <div>
                                <label htmlFor="search-userId" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    User ID
                                </label>
                                <input
                                    id="search-userId"
                                    type="text"
                                    value={searchUserId}
                                    onChange={(e) => setSearchUserId(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-mono"
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label htmlFor="search-limit" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        Limit: {searchLimit}
                                    </label>
                                    <input
                                        id="search-limit"
                                        type="range"
                                        min="1"
                                        max="50"
                                        value={searchLimit}
                                        onChange={(e) => setSearchLimit(Number(e.target.value))}
                                        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                                    />
                                </div>
                                <div>
                                    <label htmlFor="search-threshold" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        Threshold: {searchThreshold.toFixed(2)}
                                    </label>
                                    <input
                                        id="search-threshold"
                                        type="range"
                                        min="0"
                                        max="1"
                                        step="0.05"
                                        value={searchThreshold}
                                        onChange={(e) => setSearchThreshold(Number(e.target.value))}
                                        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                                    />
                                </div>
                            </div>

                            {/* Search Mode Toggle */}
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                                    Search Mode
                                </label>
                                <div className="grid grid-cols-2 gap-2">
                                    <button
                                        type="button"
                                        onClick={() => setSearchMode('fast')}
                                        className={`p-3 rounded-md border-2 font-semibold text-sm transition-all ${
                                            searchMode === 'fast'
                                                ? 'bg-blue-600 border-blue-700 text-white'
                                                : 'bg-gray-50 dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600'
                                        }`}
                                    >
                                        <div>⚡ Fast</div>
                                        <div className="text-xs font-normal mt-1 opacity-90">
                                            Cache + Conversations
                                        </div>
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setSearchMode('deep')}
                                        className={`p-3 rounded-md border-2 font-semibold text-sm transition-all ${
                                            searchMode === 'deep'
                                                ? 'bg-purple-600 border-purple-700 text-white'
                                                : 'bg-gray-50 dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600'
                                        }`}
                                    >
                                        <div>🧠 Deep</div>
                                        <div className="text-xs font-normal mt-1 opacity-90">
                                            + Atomic Notes + Graph
                                        </div>
                                    </button>
                                </div>
                            </div>

                            <button
                                onClick={handleSearch}
                                disabled={searchLoading}
                                className="w-full px-4 py-3 bg-blue-600 text-white font-semibold rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                                {searchLoading ? "Searching..." : "Search"}
                            </button>

                            {searchError && (
                                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md p-3">
                                    <p className="text-red-800 dark:text-red-300 text-sm">❌ {searchError}</p>
                                </div>
                            )}

                            {searchResult && (
                                <div className="space-y-2">
                                    <LatencyBadge latencyMs={searchResult.latency_ms} targetMs={300} label="Search" />
                                    {searchResult.mode && (
                                        <div className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${
                                            searchResult.mode === 'deep'
                                                ? 'bg-purple-100 text-purple-800 border border-purple-200'
                                                : 'bg-blue-100 text-blue-800 border border-blue-200'
                                        }`}>
                                            {searchResult.mode === 'deep' ? '🧠 Deep Mode' : '⚡ Fast Mode'}
                                        </div>
                                    )}
                                    <div className="text-sm text-gray-600 dark:text-gray-400">
                                        Found {searchResult.count} result(s)
                                    </div>
                                </div>
                            )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Search Results */}
                {searchResult && searchResult.results.length > 0 && (
                    <div className="mt-8">
                        <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">
                            Search Results ({searchResult.count})
                        </h2>
                        {searchResult.results.map((result) => {
                            // Check if this is an atomic note or a conversation
                            const isAtomicNote = result.content !== undefined;

                            if (isAtomicNote) {
                                // Render atomic note
                                return (
                                    <div
                                        key={result.id}
                                        className="border-2 border-purple-600 dark:border-purple-500 rounded-lg p-4 mb-4 bg-gray-50 dark:bg-gray-800"
                                    >
                                        <div className="flex justify-between items-start mb-3">
                                            <div className="flex flex-wrap gap-2">
                                                <span className="bg-purple-600 text-white px-2 py-1 rounded-full text-xs font-semibold">
                                                    📝 Atomic Note
                                                </span>
                                                {result.source && (
                                                    <span className={`text-white px-2 py-1 rounded-full text-xs ${
                                                        result.source === 'graph_traversal' ? 'bg-orange-600' : 'bg-blue-600'
                                                    }`}>
                                                        {result.source === 'graph_traversal' ? '🔗 Graph' : '🎯 Direct'}
                                                    </span>
                                                )}
                                                <span className="bg-gray-200 text-gray-600 px-2 py-1 rounded text-xs">
                                                    {result.note_type}
                                                </span>
                                            </div>
                                            <div className="text-right text-xs text-gray-600 dark:text-gray-400 space-y-1">
                                                {result.score !== undefined && (
                                                    <div>Score: {result.score.toFixed(3)}</div>
                                                )}
                                                {result.confidence !== undefined && (
                                                    <div>Confidence: {result.confidence.toFixed(2)}</div>
                                                )}
                                            </div>
                                        </div>

                                        <div className="text-base font-medium text-gray-900 dark:text-gray-100 mb-2">
                                            {result.content}
                                        </div>

                                        {result.context && (
                                            <div className="text-sm text-gray-600 dark:text-gray-400 italic mb-2">
                                                Context: {result.context}
                                            </div>
                                        )}

                                        {result.tags && result.tags.length > 0 && (
                                            <div className="flex flex-wrap gap-1.5 mt-2">
                                                {result.tags.map((tag, idx) => (
                                                    <span
                                                        key={idx}
                                                        className="bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full text-xs"
                                                    >
                                                        #{tag}
                                                    </span>
                                                ))}
                                            </div>
                                        )}

                                        {result.depth !== undefined && result.depth > 0 && (
                                            <div className="text-xs text-orange-600 mt-2 font-semibold">
                                                🔗 Found via {result.relationship_type} relationship (depth: {result.depth})
                                            </div>
                                        )}
                                    </div>
                                );
                            } else {
                                // Render conversation turn
                                return (
                                    <div key={result.id} className="mb-4">
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
                                        {/* Show source indicator for multi-tier search */}
                                        {result.source && (
                                            <div className="text-xs text-gray-600 dark:text-gray-400 -mt-2 mb-3 pl-4">
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
        </div>
    );
};

export default DevToolsPage;
