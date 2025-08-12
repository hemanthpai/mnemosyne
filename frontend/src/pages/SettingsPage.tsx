import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
    buildMemoryGraphForAllUsers,
    fetchModels,
    getPromptTokenCounts,
    getSettings,
    updateSettings,
    validateEndpoint,
} from "../services/api";
import { LLMSettings } from "../types/index";

type SettingsTab =
    | "prompts"
    | "llm"
    | "embeddings"
    | "parameters"
    | "search"
    | "consolidation"
    | "graph";

const SettingsPage: React.FC = () => {
    const [settings, setSettings] = useState<LLMSettings | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [saving, setSaving] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<boolean>(false);
    const [activeTab, setActiveTab] = useState<SettingsTab>("prompts");
    const [showExtractionPreview, setShowExtractionPreview] = useState(false);
    const [showSearchPreview, setShowSearchPreview] = useState(false);

    // Graph build state
    const [buildingGraph, setBuildingGraph] = useState<boolean>(false);
    const [graphBuildStatus, setGraphBuildStatus] = useState<string | null>(
        null
    );
    const [graphBuildError, setGraphBuildError] = useState<string | null>(null);
    const [pollingInterval, setPollingInterval] =
        useState<NodeJS.Timeout | null>(null);

    // Refs for textareas
    const extractionPromptRef = useRef<HTMLTextAreaElement>(null);
    const searchPromptRef = useRef<HTMLTextAreaElement>(null);

    // Token counts state
    const [tokenCounts, setTokenCounts] = useState<{
        memory_extraction_prompt: number;
        memory_search_prompt: number;
        semantic_connection_prompt: number;
        memory_summarization_prompt: number;
    } | null>(null);
    const [tokenCountsLoading, setTokenCountsLoading] = useState(false);

    // URL validation and model fetching state
    const [endpointValidation, setEndpointValidation] = useState<{
        extraction: {
            isValid: boolean | null;
            error?: string;
            isValidating: boolean;
        };
        embeddings: {
            isValid: boolean | null;
            error?: string;
            isValidating: boolean;
        };
    }>({
        extraction: { isValid: null, error: undefined, isValidating: false },
        embeddings: { isValid: null, error: undefined, isValidating: false },
    });

    const [availableModels, setAvailableModels] = useState<{
        extraction: string[];
        embeddings: string[];
    }>({
        extraction: [],
        embeddings: [],
    });

    const [modelsLoading, setModelsLoading] = useState<{
        extraction: boolean;
        embeddings: boolean;
    }>({
        extraction: false,
        embeddings: false,
    });

    useEffect(() => {
        const fetchSettings = async () => {
            try {
                const fetchedSettings = await getSettings();
                setSettings(fetchedSettings);

                // If graph is currently building, start polling for status
                if (fetchedSettings.graph_build_status === "building") {
                    startPollingGraphStatus();
                }
            } catch (err) {
                setError("Failed to fetch settings");
                console.error("Error fetching settings:", err);
            } finally {
                setLoading(false);
            }
        };

        fetchSettings();
    }, []);

    // Cleanup polling interval on unmount
    useEffect(() => {
        return () => {
            if (pollingInterval) {
                clearInterval(pollingInterval);
            }
        };
    }, [pollingInterval]);

    const fetchTokenCounts = async () => {
        if (!settings) return;

        setTokenCountsLoading(true);
        try {
            const result = await getPromptTokenCounts();
            if (result.success && result.token_counts) {
                setTokenCounts(result.token_counts);
            }
        } catch (error) {
            console.error("Error fetching token counts:", error);
        } finally {
            setTokenCountsLoading(false);
        }
    };

    useEffect(() => {
        if (settings) {
            fetchTokenCounts();
        }
    }, [settings?.extraction_model]); // Refetch when model changes

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!settings) return;

        setSaving(true);
        setError(null);
        setSuccess(false);

        try {
            const updatedSettings = await updateSettings(settings);
            setSettings(updatedSettings);
            setSuccess(true);
            setTimeout(() => setSuccess(false), 3000);
        } catch (err) {
            setError("Failed to update settings");
            console.error("Error updating settings:", err);
        } finally {
            setSaving(false);
        }
    };

    const handleInputChange = (field: keyof LLMSettings, value: string) => {
        if (!settings) return;
        setSettings({ ...settings, [field]: value });
    };

    // Graph-related functions
    const startPollingGraphStatus = () => {
        // Clear any existing interval
        if (pollingInterval) {
            clearInterval(pollingInterval);
        }

        const interval = setInterval(async () => {
            try {
                // Check the global build status from settings
                const updatedSettings = await getSettings();
                setSettings(updatedSettings);

                if (updatedSettings.graph_build_status !== "building") {
                    setBuildingGraph(false);
                    clearInterval(interval);
                    setPollingInterval(null);

                    if (updatedSettings.graph_build_status === "failed") {
                        setGraphBuildError(
                            "Graph build failed. Please check your Neo4j connection and try again."
                        );
                    } else if (updatedSettings.graph_build_status === "built") {
                        setGraphBuildStatus("Graph built successfully!");
                        setTimeout(() => setGraphBuildStatus(null), 5000);
                    } else if (
                        updatedSettings.graph_build_status === "partial"
                    ) {
                        setGraphBuildStatus(
                            "Graph partially built - some users failed."
                        );
                        setTimeout(() => setGraphBuildStatus(null), 5000);
                    }
                }
            } catch (error) {
                console.error("Error polling graph status:", error);
            }
        }, 2000); // Poll every 2 seconds

        setPollingInterval(interval);
    };

    const handleGraphToggle = async () => {
        if (!settings) return;

        if (!settings.enable_graph_enhanced_retrieval) {
            // Enable and trigger build for ALL users
            setBuildingGraph(true);
            setGraphBuildError(null);
            setGraphBuildStatus("Initiating graph build for all users...");

            try {
                // First, update the setting to enable graph retrieval
                const updatedSettings = {
                    ...settings,
                    enable_graph_enhanced_retrieval: true,
                    graph_build_status: "building" as const,
                };

                await updateSettings(updatedSettings);
                setSettings(updatedSettings);

                // Then trigger the graph build for ALL users (full build when first enabling)
                console.log("About to call buildMemoryGraphForAllUsers...");
                const buildResult = await buildMemoryGraphForAllUsers(false);
                console.log("Build result:", buildResult);

                if (buildResult.success) {
                    // Build is complete! Update status immediately
                    setBuildingGraph(false);
                    setGraphBuildStatus("Graph built successfully!");
                    
                    // Update settings to reflect completed build
                    const completedSettings = {
                        ...settings,
                        enable_graph_enhanced_retrieval: true,
                        graph_build_status: "built" as const,
                    };
                    console.log("Setting completed settings:", completedSettings);
                    setSettings(completedSettings);
                    
                    // Clear status message after a few seconds
                    setTimeout(() => setGraphBuildStatus(null), 5000);
                } else {
                    setBuildingGraph(false);
                    const errorMessage = buildResult.error || "Failed to start graph build";
                    
                    // Check for Neo4j-specific error
                    if (errorMessage.includes("Neo4j database connection failed")) {
                        setGraphBuildError(
                            "Neo4j database connection failed. Please ensure Neo4j is running on localhost:7687 with correct credentials (neo4j/password)."
                        );
                    } else {
                        setGraphBuildError(errorMessage);
                    }
                    
                    // Revert the setting
                    const revertedSettings = {
                        ...settings,
                        enable_graph_enhanced_retrieval: false,
                        graph_build_status: "failed" as const,
                    };
                    await updateSettings(revertedSettings);
                    setSettings(revertedSettings);
                }
            } catch (error) {
                console.error("Error enabling graph retrieval:", error);
                setBuildingGraph(false);
                setGraphBuildError("Failed to enable graph retrieval");
                // Revert the setting
                const revertedSettings = {
                    ...settings,
                    enable_graph_enhanced_retrieval: false,
                    graph_build_status: "failed" as const,
                };
                await updateSettings(revertedSettings);
                setSettings(revertedSettings);
            }
        } else {
            // Disable graph retrieval
            try {
                const updatedSettings = {
                    ...settings,
                    enable_graph_enhanced_retrieval: false,
                };
                await updateSettings(updatedSettings);
                setSettings(updatedSettings);
                setGraphBuildStatus("Graph retrieval disabled");
                setTimeout(() => setGraphBuildStatus(null), 3000);
            } catch (error) {
                console.error("Error disabling graph retrieval:", error);
                setError("Failed to disable graph retrieval");
            }
        }
    };

    // Debounced URL validation
    const validateEndpointUrl = useCallback(
        async (
            type: "extraction" | "embeddings",
            url: string,
            providerType: string,
            apiKey?: string
        ) => {
            if (!url.trim()) {
                setEndpointValidation((prev) => ({
                    ...prev,
                    [type]: {
                        isValid: null,
                        error: undefined,
                        isValidating: false,
                    },
                }));
                return;
            }

            setEndpointValidation((prev) => ({
                ...prev,
                [type]: { isValid: null, error: undefined, isValidating: true },
            }));

            try {
                const result = await validateEndpoint(
                    url,
                    providerType,
                    apiKey
                );
                setEndpointValidation((prev) => ({
                    ...prev,
                    [type]: {
                        isValid: result.success,
                        error: result.error,
                        isValidating: false,
                    },
                }));

                // If validation successful, fetch models
                if (result.success) {
                    await fetchModelsForEndpoint(
                        type,
                        url,
                        providerType,
                        apiKey
                    );
                }
            } catch (error: any) {
                setEndpointValidation((prev) => ({
                    ...prev,
                    [type]: {
                        isValid: false,
                        error: error.message || "Failed to validate endpoint",
                        isValidating: false,
                    },
                }));
            }
        },
        []
    );

    const fetchModelsForEndpoint = useCallback(
        async (
            type: "extraction" | "embeddings",
            url: string,
            providerType: string,
            apiKey?: string
        ) => {
            setModelsLoading((prev) => ({ ...prev, [type]: true }));

            try {
                const result = await fetchModels(url, providerType, apiKey);
                if (result.success && result.models) {
                    setAvailableModels((prev) => ({
                        ...prev,
                        [type]: result.models || [],
                    }));
                } else {
                    console.warn(
                        `Failed to fetch models for ${type}:`,
                        result.error
                    );
                }
            } catch (error: any) {
                console.error(`Error fetching models for ${type}:`, error);
            } finally {
                setModelsLoading((prev) => ({ ...prev, [type]: false }));
            }
        },
        []
    );

    // Debounced validation with timeout
    useEffect(() => {
        if (!settings) return;

        const timeoutId = setTimeout(() => {
            if (settings.extraction_endpoint_url) {
                validateEndpointUrl(
                    "extraction",
                    settings.extraction_endpoint_url,
                    settings.extraction_provider_type,
                    settings.extraction_endpoint_api_key
                );
            }
        }, 1000);

        return () => clearTimeout(timeoutId);
    }, [
        settings?.extraction_endpoint_url,
        settings?.extraction_provider_type,
        settings?.extraction_endpoint_api_key,
        validateEndpointUrl,
    ]);

    useEffect(() => {
        if (!settings) return;

        const timeoutId = setTimeout(() => {
            if (settings.embeddings_endpoint_url) {
                validateEndpointUrl(
                    "embeddings",
                    settings.embeddings_endpoint_url,
                    settings.embeddings_provider_type,
                    settings.embeddings_endpoint_api_key
                );
            }
        }, 1000);

        return () => clearTimeout(timeoutId);
    }, [
        settings?.embeddings_endpoint_url,
        settings?.embeddings_provider_type,
        settings?.embeddings_endpoint_api_key,
        validateEndpointUrl,
    ]);

    const tabs = [
        { id: "prompts" as SettingsTab, name: "Prompts", icon: "📝" },
        { id: "llm" as SettingsTab, name: "LLM Endpoints", icon: "🤖" },
        { id: "embeddings" as SettingsTab, name: "Embeddings", icon: "🔍" },
        { id: "parameters" as SettingsTab, name: "LLM Parameters", icon: "⚙️" },
        { id: "search" as SettingsTab, name: "Search Config", icon: "🎯" },
        {
            id: "consolidation" as SettingsTab,
            name: "Memory Consolidation",
            icon: "🔗",
        },
        {
            id: "graph" as SettingsTab,
            name: "Graph-Enhanced Retrieval",
            icon: "🕸️",
        },
    ];

    // URL validation indicator component
    const ValidationIndicator: React.FC<{
        isValid: boolean | null;
        error?: string;
        isValidating: boolean;
    }> = ({ isValid, error, isValidating }) => {
        if (isValidating) {
            return (
                <div className="flex items-center space-x-2 text-sm text-blue-600">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                    <span>Validating...</span>
                </div>
            );
        }

        if (isValid === null) {
            return null;
        }

        if (isValid) {
            return (
                <div className="flex items-center space-x-2 text-sm text-green-600">
                    <svg
                        className="w-4 h-4"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                    >
                        <path
                            fillRule="evenodd"
                            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                            clipRule="evenodd"
                        />
                    </svg>
                    <span>Endpoint valid</span>
                </div>
            );
        }

        return (
            <div className="flex items-center space-x-2 text-sm text-red-600">
                <svg
                    className="w-4 h-4"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                >
                    <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                        clipRule="evenodd"
                    />
                </svg>
                <span>{error || "Endpoint invalid"}</span>
            </div>
        );
    };

    const TokenCountBadge: React.FC<{
        count: number | undefined;
        loading: boolean;
        label: string;
    }> = ({ count, loading, label }) => {
        if (loading) {
            return (
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-gray-100 text-gray-600">
                    <div className="animate-spin rounded-full h-3 w-3 border-b border-gray-600 mr-1"></div>
                    Calculating...
                </span>
            );
        }

        if (count === undefined) return null;

        const getColorClass = (tokenCount: number) => {
            if (tokenCount < 1000) return "bg-green-100 text-green-800";
            if (tokenCount < 2000) return "bg-yellow-100 text-yellow-800";
            if (tokenCount < 4000) return "bg-orange-100 text-orange-800";
            return "bg-red-100 text-red-800";
        };

        return (
            <span
                className={`inline-flex items-center px-2 py-1 rounded-full text-xs ${getColorClass(
                    count
                )}`}
            >
                {label}: {count.toLocaleString()} tokens
            </span>
        );
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                    <p className="mt-2 text-gray-600">Loading settings...</p>
                </div>
            </div>
        );
    }

    if (!settings) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                    <p className="text-red-600 mb-4">Failed to load settings</p>
                    <Link
                        to="/"
                        className="inline-flex items-center px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors duration-200"
                    >
                        ← Back to Home
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Header */}
            <header className="bg-white shadow-sm">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center py-6">
                        <div className="flex items-center">
                            <h1 className="text-3xl font-bold text-gray-900">
                                Settings
                            </h1>
                            <span className="ml-3 text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                                Configuration
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
                <div className="bg-white shadow rounded-lg">
                    {/* Description Section */}
                    <div className="px-6 py-4 border-b border-gray-200">
                        <div>
                            <h2 className="text-xl font-semibold text-gray-900 mb-2">
                                System Configuration
                            </h2>
                            <p className="text-gray-600">
                                Configure your LLM endpoints, generation
                                parameters, search settings, and system prompts.
                            </p>
                        </div>
                    </div>

                    {/* Tabs */}
                    <div className="border-b border-gray-200">
                        <nav
                            className="flex space-x-8 px-6 overflow-x-auto"
                            aria-label="Tabs"
                        >
                            {tabs.map((tab) => (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`${
                                        activeTab === tab.id
                                            ? "border-blue-500 text-blue-600"
                                            : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                                    } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center space-x-2`}
                                >
                                    <span>{tab.icon}</span>
                                    <span>{tab.name}</span>
                                </button>
                            ))}
                        </nav>
                    </div>

                    <form onSubmit={handleSubmit} className="px-6 py-6">
                        {/* Prompts Tab */}
                        {activeTab === "prompts" && (
                            <div className="space-y-8">
                                {/* Add refresh button for token counts */}
                                <div className="flex justify-between items-center">
                                    <div>
                                        <h2 className="text-xl font-semibold text-gray-900">
                                            System Prompts
                                        </h2>
                                        <p className="text-sm text-gray-600">
                                            Configure the prompts used for
                                            memory extraction, search, and
                                            analysis.
                                        </p>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={fetchTokenCounts}
                                        disabled={tokenCountsLoading}
                                        className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                                    >
                                        {tokenCountsLoading ? (
                                            <>
                                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-700 mr-2"></div>
                                                Calculating...
                                            </>
                                        ) : (
                                            <>
                                                <svg
                                                    className="w-4 h-4 mr-2"
                                                    fill="none"
                                                    stroke="currentColor"
                                                    viewBox="0 0 24 24"
                                                >
                                                    <path
                                                        strokeLinecap="round"
                                                        strokeLinejoin="round"
                                                        strokeWidth={2}
                                                        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                                                    />
                                                </svg>
                                                Refresh Token Counts
                                            </>
                                        )}
                                    </button>
                                </div>

                                {/* Memory Extraction Prompt */}
                                <div>
                                    <div className="flex items-center justify-between mb-4">
                                        <div className="flex-1">
                                            <div className="flex items-center space-x-3">
                                                <h3 className="text-lg font-medium text-gray-900">
                                                    Memory Extraction Prompt
                                                </h3>
                                                <TokenCountBadge
                                                    count={
                                                        tokenCounts?.memory_extraction_prompt
                                                    }
                                                    loading={tokenCountsLoading}
                                                    label="Size"
                                                />
                                            </div>
                                            <p className="text-sm text-gray-600">
                                                Prompt used to extract memories
                                                from conversations with flexible
                                                tagging
                                            </p>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() =>
                                                setShowExtractionPreview(
                                                    !showExtractionPreview
                                                )
                                            }
                                            className="text-sm text-blue-600 hover:text-blue-800"
                                        >
                                            {showExtractionPreview
                                                ? "Hide Preview"
                                                : "Show Preview"}
                                        </button>
                                    </div>

                                    <textarea
                                        ref={extractionPromptRef}
                                        value={
                                            settings.memory_extraction_prompt
                                        }
                                        onChange={(e) => {
                                            handleInputChange(
                                                "memory_extraction_prompt",
                                                e.target.value
                                            );
                                        }}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                                        rows={20}
                                        placeholder="Prompt for the LLM to extract memories from conversations"
                                    />

                                    {showExtractionPreview && (
                                        <div className="mt-4 p-4 bg-gray-50 border rounded-md">
                                            <div className="text-sm font-medium text-gray-700 mb-2">
                                                Current Prompt:
                                            </div>
                                            <pre className="text-xs text-gray-600 whitespace-pre-wrap overflow-auto max-h-64">
                                                {
                                                    settings.memory_extraction_prompt
                                                }
                                            </pre>
                                        </div>
                                    )}

                                    <div className="mt-2 text-xs text-gray-500">
                                        This prompt uses flexible tagging
                                        without predefined categories. The AI
                                        will generate contextual tags based on
                                        the content.
                                    </div>
                                </div>

                                {/* Memory Search Prompt */}
                                <div className="border-t pt-8">
                                    <div className="flex items-center justify-between mb-4">
                                        <div className="flex-1">
                                            <div className="flex items-center space-x-3">
                                                <h3 className="text-lg font-medium text-gray-900">
                                                    Memory Search Prompt
                                                </h3>
                                                <TokenCountBadge
                                                    count={
                                                        tokenCounts?.memory_search_prompt
                                                    }
                                                    loading={tokenCountsLoading}
                                                    label="Size"
                                                />
                                            </div>
                                            <p className="text-sm text-gray-600">
                                                Prompt used to generate search
                                                queries for retrieving relevant
                                                memories
                                            </p>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() =>
                                                setShowSearchPreview(
                                                    !showSearchPreview
                                                )
                                            }
                                            className="text-sm text-blue-600 hover:text-blue-800"
                                        >
                                            {showSearchPreview
                                                ? "Hide Preview"
                                                : "Show Preview"}
                                        </button>
                                    </div>

                                    <textarea
                                        ref={searchPromptRef}
                                        value={settings.memory_search_prompt}
                                        onChange={(e) =>
                                            handleInputChange(
                                                "memory_search_prompt",
                                                e.target.value
                                            )
                                        }
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                                        rows={20}
                                        placeholder="Prompt for the LLM to generate search queries"
                                    />

                                    {showSearchPreview && (
                                        <div className="mt-4 p-4 bg-gray-50 border rounded-md">
                                            <div className="text-sm font-medium text-gray-700 mb-2">
                                                Current Prompt:
                                            </div>
                                            <pre className="text-xs text-gray-600 whitespace-pre-wrap overflow-auto max-h-64">
                                                {settings.memory_search_prompt}
                                            </pre>
                                        </div>
                                    )}

                                    <div className="mt-2 text-xs text-gray-500">
                                        This prompt generates multiple search
                                        strategies to find relevant memories
                                        through direct, semantic, and contextual
                                        queries.
                                    </div>
                                </div>

                                {/* Semantic Connection Prompt */}
                                <div className="border-t pt-8">
                                    <div className="flex items-center space-x-3 mb-4">
                                        <h3 className="text-lg font-medium text-gray-900">
                                            Semantic Connection Analysis Prompt
                                        </h3>
                                        <TokenCountBadge
                                            count={
                                                tokenCounts?.semantic_connection_prompt
                                            }
                                            loading={tokenCountsLoading}
                                            label="Size"
                                        />
                                    </div>
                                    <textarea
                                        value={
                                            settings.semantic_connection_prompt
                                        }
                                        onChange={(e) =>
                                            handleInputChange(
                                                "semantic_connection_prompt",
                                                e.target.value
                                            )
                                        }
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                                        rows={10}
                                    />
                                </div>

                                {/* Memory Summarization Prompt */}
                                <div className="border-t pt-8">
                                    <div className="flex items-center space-x-3 mb-4">
                                        <h3 className="text-lg font-medium text-gray-900">
                                            Memory Summarization Prompt
                                        </h3>
                                        <TokenCountBadge
                                            count={
                                                tokenCounts?.memory_summarization_prompt
                                            }
                                            loading={tokenCountsLoading}
                                            label="Size"
                                        />
                                    </div>
                                    <textarea
                                        value={
                                            settings.memory_summarization_prompt
                                        }
                                        onChange={(e) =>
                                            handleInputChange(
                                                "memory_summarization_prompt",
                                                e.target.value
                                            )
                                        }
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                                        rows={10}
                                    />
                                </div>
                            </div>
                        )}

                        {/* LLM Endpoints Tab */}
                        {activeTab === "llm" && (
                            <div className="space-y-6">
                                <div>
                                    <h3 className="text-lg font-medium text-gray-900 mb-4">
                                        Memory Extraction LLM
                                    </h3>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Provider Type
                                            </label>
                                            <select
                                                value={
                                                    settings.extraction_provider_type
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "extraction_provider_type",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            >
                                                <option value="openai">
                                                    OpenAI
                                                </option>
                                                <option value="openai_compatible">
                                                    OpenAI Compatible
                                                </option>
                                                <option value="ollama">
                                                    Ollama
                                                </option>
                                            </select>
                                        </div>

                                        <div className="md:col-span-2">
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Endpoint URL
                                            </label>
                                            <input
                                                type="url"
                                                value={
                                                    settings.extraction_endpoint_url
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "extraction_endpoint_url",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                placeholder="http://localhost:11434"
                                            />
                                            <div className="mt-2">
                                                <ValidationIndicator
                                                    isValid={
                                                        endpointValidation
                                                            .extraction.isValid
                                                    }
                                                    error={
                                                        endpointValidation
                                                            .extraction.error
                                                    }
                                                    isValidating={
                                                        endpointValidation
                                                            .extraction
                                                            .isValidating
                                                    }
                                                />
                                            </div>
                                        </div>

                                        <div className="md:col-span-2">
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                API Key
                                            </label>
                                            <input
                                                type="password"
                                                value={
                                                    settings.extraction_endpoint_api_key
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "extraction_endpoint_api_key",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                placeholder="Your API key (leave empty if not needed)"
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Model
                                                {modelsLoading.extraction && (
                                                    <span className="ml-2 text-xs text-blue-600">
                                                        Loading models...
                                                    </span>
                                                )}
                                            </label>
                                            {availableModels.extraction.length >
                                            0 ? (
                                                <select
                                                    value={
                                                        settings.extraction_model
                                                    }
                                                    onChange={(e) =>
                                                        handleInputChange(
                                                            "extraction_model",
                                                            e.target.value
                                                        )
                                                    }
                                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                >
                                                    <option value="">
                                                        Select a model
                                                    </option>
                                                    {availableModels.extraction.map(
                                                        (model) => (
                                                            <option
                                                                key={model}
                                                                value={model}
                                                            >
                                                                {model}
                                                            </option>
                                                        )
                                                    )}
                                                </select>
                                            ) : (
                                                <input
                                                    type="text"
                                                    value={
                                                        settings.extraction_model
                                                    }
                                                    onChange={(e) =>
                                                        handleInputChange(
                                                            "extraction_model",
                                                            e.target.value
                                                        )
                                                    }
                                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                    placeholder="e.g., gpt-4, llama3 (validate endpoint to see available models)"
                                                />
                                            )}
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Timeout (seconds)
                                            </label>
                                            <input
                                                type="number"
                                                value={
                                                    settings.extraction_timeout
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "extraction_timeout",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                placeholder="30"
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Embeddings Tab */}
                        {activeTab === "embeddings" && (
                            <div className="space-y-6">
                                <div>
                                    <h3 className="text-lg font-medium text-gray-900 mb-4">
                                        Embeddings API
                                    </h3>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Provider Type
                                            </label>
                                            <select
                                                value={
                                                    settings.embeddings_provider_type
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "embeddings_provider_type",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            >
                                                <option value="openai_compatible">
                                                    OpenAI Compatible
                                                </option>
                                                <option value="ollama">
                                                    Ollama
                                                </option>
                                            </select>
                                        </div>

                                        <div className="md:col-span-2">
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Endpoint URL
                                            </label>
                                            <input
                                                type="url"
                                                value={
                                                    settings.embeddings_endpoint_url
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "embeddings_endpoint_url",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                placeholder="http://localhost:11434"
                                            />
                                            <div className="mt-2">
                                                <ValidationIndicator
                                                    isValid={
                                                        endpointValidation
                                                            .embeddings.isValid
                                                    }
                                                    error={
                                                        endpointValidation
                                                            .embeddings.error
                                                    }
                                                    isValidating={
                                                        endpointValidation
                                                            .embeddings
                                                            .isValidating
                                                    }
                                                />
                                            </div>
                                        </div>

                                        <div className="md:col-span-2">
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                API Key
                                            </label>
                                            <input
                                                type="password"
                                                value={
                                                    settings.embeddings_endpoint_api_key
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "embeddings_endpoint_api_key",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                placeholder="Your API key (leave empty if not needed)"
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Model
                                                {modelsLoading.embeddings && (
                                                    <span className="ml-2 text-xs text-blue-600">
                                                        Loading models...
                                                    </span>
                                                )}
                                            </label>
                                            {availableModels.embeddings.length >
                                            0 ? (
                                                <select
                                                    value={
                                                        settings.embeddings_model
                                                    }
                                                    onChange={(e) =>
                                                        handleInputChange(
                                                            "embeddings_model",
                                                            e.target.value
                                                        )
                                                    }
                                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                >
                                                    <option value="">
                                                        Select a model
                                                    </option>
                                                    {availableModels.embeddings.map(
                                                        (model) => (
                                                            <option
                                                                key={model}
                                                                value={model}
                                                            >
                                                                {model}
                                                            </option>
                                                        )
                                                    )}
                                                </select>
                                            ) : (
                                                <input
                                                    type="text"
                                                    value={
                                                        settings.embeddings_model
                                                    }
                                                    onChange={(e) =>
                                                        handleInputChange(
                                                            "embeddings_model",
                                                            e.target.value
                                                        )
                                                    }
                                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                    placeholder="e.g., text-embedding-ada-002, nomic-embed-text (validate endpoint to see available models)"
                                                />
                                            )}
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Timeout (seconds)
                                            </label>
                                            <input
                                                type="number"
                                                value={
                                                    settings.embeddings_timeout
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "embeddings_timeout",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                placeholder="30"
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* LLM Parameters Tab */}
                        {activeTab === "parameters" && (
                            <div className="space-y-6">
                                <div>
                                    <h3 className="text-lg font-medium text-gray-900 mb-4">
                                        LLM Generation Parameters
                                    </h3>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Temperature
                                            </label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                min="0"
                                                max="2"
                                                value={settings.llm_temperature}
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "llm_temperature",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="text-xs text-gray-500 mt-1">
                                                Controls randomness (0.0-2.0).
                                                Lower = more deterministic.
                                            </p>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Top P
                                            </label>
                                            <input
                                                type="number"
                                                step="0.05"
                                                min="0"
                                                max="1"
                                                value={settings.llm_top_p}
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "llm_top_p",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="text-xs text-gray-500 mt-1">
                                                Nucleus sampling (0.0-1.0).
                                                Controls diversity of output.
                                            </p>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Top K
                                            </label>
                                            <input
                                                type="number"
                                                min="1"
                                                value={settings.llm_top_k}
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "llm_top_k",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="text-xs text-gray-500 mt-1">
                                                Limits the number of tokens
                                                considered for each step.
                                            </p>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Max Tokens
                                            </label>
                                            <input
                                                type="number"
                                                min="1"
                                                value={settings.llm_max_tokens}
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "llm_max_tokens",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="text-xs text-gray-500 mt-1">
                                                Maximum number of tokens to
                                                generate.
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Search Configuration Tab */}
                        {activeTab === "search" && (
                            <div className="space-y-6">
                                {/* Semantic Enhancement */}
                                <div>
                                    <h3 className="text-lg font-medium text-gray-900 mb-4">
                                        Semantic Enhancement
                                    </h3>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div className="md:col-span-2">
                                            <label className="flex items-center">
                                                <input
                                                    type="checkbox"
                                                    checked={
                                                        settings.enable_semantic_connections
                                                    }
                                                    onChange={(e) =>
                                                        handleInputChange(
                                                            "enable_semantic_connections",
                                                            e.target.checked.toString()
                                                        )
                                                    }
                                                    className="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50"
                                                />
                                                <span className="ml-2 text-sm text-gray-700">
                                                    Enable semantic connection
                                                    enhancement
                                                </span>
                                            </label>
                                            <p className="text-xs text-gray-500 mt-1">
                                                Find additional memories through
                                                semantic analysis
                                            </p>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Enhancement Threshold
                                            </label>
                                            <input
                                                type="number"
                                                min="1"
                                                value={
                                                    settings.semantic_enhancement_threshold
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "semantic_enhancement_threshold",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="text-xs text-gray-500 mt-1">
                                                Minimum memories needed to
                                                trigger enhancement
                                            </p>
                                        </div>
                                    </div>
                                </div>

                                {/* Search Type Thresholds */}
                                <div className="border-t pt-6">
                                    <h3 className="text-lg font-medium text-gray-900 mb-4">
                                        Search Type Thresholds
                                    </h3>
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Direct Search
                                            </label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                min="0"
                                                max="1"
                                                value={
                                                    settings.search_threshold_direct
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "search_threshold_direct",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="text-xs text-gray-500 mt-1">
                                                Threshold for explicit matches
                                            </p>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Semantic Search
                                            </label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                min="0"
                                                max="1"
                                                value={
                                                    settings.search_threshold_semantic
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "search_threshold_semantic",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="text-xs text-gray-500 mt-1">
                                                Threshold for related concepts
                                            </p>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Experiential Search
                                            </label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                min="0"
                                                max="1"
                                                value={
                                                    settings.search_threshold_experiential
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "search_threshold_experiential",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="text-xs text-gray-500 mt-1">
                                                Threshold for experience-based
                                            </p>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Contextual Search
                                            </label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                min="0"
                                                max="1"
                                                value={
                                                    settings.search_threshold_contextual
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "search_threshold_contextual",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="text-xs text-gray-500 mt-1">
                                                Threshold for situational
                                                relevance
                                            </p>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Interest Search
                                            </label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                min="0"
                                                max="1"
                                                value={
                                                    settings.search_threshold_interest
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "search_threshold_interest",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="text-xs text-gray-500 mt-1">
                                                Threshold for general interests
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Memory Consolidation Tab */}
                        {activeTab === "consolidation" && (
                            <div className="space-y-6">
                                <div>
                                    <h3 className="text-lg font-medium text-gray-900 mb-4">
                                        Memory Consolidation Settings
                                    </h3>
                                    <p className="text-sm text-gray-600 mb-6">
                                        Configure automatic detection and
                                        merging of duplicate or highly similar
                                        memories to prevent information
                                        redundancy.
                                    </p>

                                    {/* Enable Consolidation */}
                                    <div className="bg-gray-50 p-4 rounded-lg mb-6">
                                        <div className="flex items-center">
                                            <label className="flex items-center cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    checked={
                                                        settings.enable_memory_consolidation
                                                    }
                                                    onChange={(e) =>
                                                        handleInputChange(
                                                            "enable_memory_consolidation",
                                                            e.target.checked.toString()
                                                        )
                                                    }
                                                    className="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50 h-5 w-5"
                                                />
                                                <span className="ml-3 text-base font-medium text-gray-900">
                                                    Enable Memory Consolidation
                                                </span>
                                            </label>
                                        </div>
                                        <p className="text-sm text-gray-600 mt-2 ml-8">
                                            Automatically detect and merge
                                            duplicate or highly similar memories
                                            during the extraction process.
                                        </p>
                                    </div>

                                    {/* Consolidation Settings Grid */}
                                    <div
                                        className={`grid grid-cols-1 md:grid-cols-2 gap-6 ${
                                            !settings.enable_memory_consolidation
                                                ? "opacity-50 pointer-events-none"
                                                : ""
                                        }`}
                                    >
                                        {/* Similarity Threshold */}
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                Duplicate Detection Threshold
                                                <span className="ml-1 text-blue-600 text-xs">
                                                    {(
                                                        settings.consolidation_similarity_threshold *
                                                        100
                                                    ).toFixed(0)}
                                                    %
                                                </span>
                                            </label>
                                            <input
                                                type="range"
                                                min="0.5"
                                                max="1.0"
                                                step="0.05"
                                                value={
                                                    settings.consolidation_similarity_threshold
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "consolidation_similarity_threshold",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                                            />
                                            <div className="flex justify-between text-xs text-gray-500 mt-1">
                                                <span>
                                                    50% (More duplicates)
                                                </span>
                                                <span>
                                                    100% (Fewer duplicates)
                                                </span>
                                            </div>
                                            <p className="text-xs text-gray-600 mt-2">
                                                How similar memories must be to
                                                be considered duplicates. Higher
                                                values are more strict.
                                            </p>
                                        </div>

                                        {/* Auto-Consolidation Threshold */}
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                Auto-Consolidation Threshold
                                                <span className="ml-1 text-green-600 text-xs">
                                                    {(
                                                        settings.consolidation_auto_threshold *
                                                        100
                                                    ).toFixed(0)}
                                                    %
                                                </span>
                                            </label>
                                            <input
                                                type="range"
                                                min="0.8"
                                                max="1.0"
                                                step="0.02"
                                                value={
                                                    settings.consolidation_auto_threshold
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "consolidation_auto_threshold",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                                            />
                                            <div className="flex justify-between text-xs text-gray-500 mt-1">
                                                <span>
                                                    80% (More automatic)
                                                </span>
                                                <span>
                                                    100% (Less automatic)
                                                </span>
                                            </div>
                                            <p className="text-xs text-gray-600 mt-2">
                                                Similarity threshold for
                                                automatic consolidation without
                                                manual review.
                                            </p>
                                        </div>

                                        {/* Consolidation Strategy */}
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                Consolidation Strategy
                                            </label>
                                            <select
                                                value={
                                                    settings.consolidation_strategy
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "consolidation_strategy",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            >
                                                <option value="automatic">
                                                    Automatic (Rule-based
                                                    merging)
                                                </option>
                                                <option value="llm_guided">
                                                    LLM Guided (AI-powered
                                                    consolidation)
                                                </option>
                                                <option value="manual">
                                                    Manual (Simple superseding)
                                                </option>
                                            </select>
                                            <div className="text-xs text-gray-600 mt-2">
                                                {settings.consolidation_strategy ===
                                                    "automatic" && (
                                                    <p>
                                                        Uses predefined rules to
                                                        merge similar memories
                                                        automatically.
                                                    </p>
                                                )}
                                                {settings.consolidation_strategy ===
                                                    "llm_guided" && (
                                                    <p>
                                                        Uses AI to intelligently
                                                        consolidate memories
                                                        while preserving
                                                        important information.
                                                    </p>
                                                )}
                                                {settings.consolidation_strategy ===
                                                    "manual" && (
                                                    <p>
                                                        Simply marks duplicates
                                                        as superseded without
                                                        changing content.
                                                    </p>
                                                )}
                                            </div>
                                        </div>

                                        {/* Max Group Size */}
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                Max Group Size
                                                <span className="ml-1 text-purple-600 text-xs">
                                                    {
                                                        settings.consolidation_max_group_size
                                                    }{" "}
                                                    memories
                                                </span>
                                            </label>
                                            <input
                                                type="range"
                                                min="2"
                                                max="10"
                                                step="1"
                                                value={
                                                    settings.consolidation_max_group_size
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "consolidation_max_group_size",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                                            />
                                            <div className="flex justify-between text-xs text-gray-500 mt-1">
                                                <span>2</span>
                                                <span>5</span>
                                                <span>10</span>
                                            </div>
                                            <p className="text-xs text-gray-600 mt-2">
                                                Maximum number of memories that
                                                can be consolidated into a
                                                single group.
                                            </p>
                                        </div>

                                        {/* Batch Size */}
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                Processing Batch Size
                                                <span className="ml-1 text-orange-600 text-xs">
                                                    {
                                                        settings.consolidation_batch_size
                                                    }
                                                </span>
                                            </label>
                                            <input
                                                type="range"
                                                min="10"
                                                max="1000"
                                                step="10"
                                                value={
                                                    settings.consolidation_batch_size
                                                }
                                                onChange={(e) =>
                                                    handleInputChange(
                                                        "consolidation_batch_size",
                                                        e.target.value
                                                    )
                                                }
                                                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                                            />
                                            <div className="flex justify-between text-xs text-gray-500 mt-1">
                                                <span>10</span>
                                                <span>500</span>
                                                <span>1000</span>
                                            </div>
                                            <p className="text-xs text-gray-600 mt-2">
                                                Number of memories to process in
                                                each consolidation batch for
                                                better performance.
                                            </p>
                                        </div>
                                    </div>

                                    {/* Validation Warning */}
                                    {settings.consolidation_similarity_threshold >=
                                        settings.consolidation_auto_threshold && (
                                        <div className="bg-amber-50 border-l-4 border-amber-400 p-4 mt-6">
                                            <div className="flex">
                                                <div className="flex-shrink-0">
                                                    <svg
                                                        className="h-5 w-5 text-amber-400"
                                                        viewBox="0 0 20 20"
                                                        fill="currentColor"
                                                    >
                                                        <path
                                                            fillRule="evenodd"
                                                            d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                                                            clipRule="evenodd"
                                                        />
                                                    </svg>
                                                </div>
                                                <div className="ml-3">
                                                    <p className="text-sm text-amber-700">
                                                        <strong>
                                                            Warning:
                                                        </strong>{" "}
                                                        Auto-consolidation
                                                        threshold should be
                                                        higher than the
                                                        detection threshold for
                                                        proper operation.
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Performance Tips */}
                                    <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mt-6">
                                        <h4 className="text-sm font-medium text-blue-900 mb-2">
                                            💡 Tips for Optimal Performance
                                        </h4>
                                        <ul className="text-sm text-blue-800 space-y-1">
                                            <li>
                                                •{" "}
                                                <strong>
                                                    Detection Threshold:
                                                </strong>{" "}
                                                Start with 85% and adjust based
                                                on your needs
                                            </li>
                                            <li>
                                                • <strong>LLM Guided:</strong>{" "}
                                                Recommended strategy for best
                                                quality consolidation
                                            </li>
                                            <li>
                                                • <strong>Batch Size:</strong>{" "}
                                                Higher values improve
                                                performance but use more memory
                                            </li>
                                            <li>
                                                • <strong>Group Size:</strong>{" "}
                                                Keep low (3-5) to avoid
                                                over-consolidation
                                            </li>
                                        </ul>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Graph-Enhanced Retrieval Tab */}
                        {activeTab === "graph" && (
                            <div className="space-y-6">
                                <div>
                                    <h3 className="text-lg font-medium text-gray-900 mb-4">
                                        Graph-Enhanced Retrieval Settings
                                    </h3>
                                    <p className="text-sm text-gray-600 mb-6">
                                        Enable hybrid search that combines
                                        vector similarity with relationship
                                        traversal for improved context
                                        discovery.
                                    </p>

                                    {/* Enable/Disable Button */}
                                    <div className="bg-gray-50 p-6 rounded-lg mb-6">
                                        <div className="flex items-center justify-between">
                                            <div className="flex-1">
                                                <h4 className="text-base font-medium text-gray-900 mb-2">
                                                    Graph-Enhanced Retrieval
                                                </h4>
                                                <p className="text-sm text-gray-600 mb-4">
                                                    Combines vector similarity
                                                    search with relationship
                                                    traversal to discover
                                                    contextually relevant
                                                    memories.
                                                </p>
                                                <div className="text-sm text-gray-500">
                                                    <strong>Status:</strong>{" "}
                                                    {buildingGraph ? (
                                                        <span className="text-blue-600">
                                                            <span className="animate-spin inline-block mr-1">
                                                                ⏳
                                                            </span>
                                                            Building...
                                                        </span>
                                                    ) : settings.enable_graph_enhanced_retrieval ? (
                                                        <span className="text-green-600">
                                                            ✓ Enabled
                                                        </span>
                                                    ) : (
                                                        <span className="text-gray-500">
                                                            ○ Disabled
                                                        </span>
                                                    )}
                                                    {settings.graph_last_build &&
                                                        !buildingGraph && (
                                                            <span className="ml-4">
                                                                <strong>
                                                                    Last Build:
                                                                </strong>{" "}
                                                                {new Date(
                                                                    settings.graph_last_build
                                                                ).toLocaleDateString()}
                                                            </span>
                                                        )}
                                                </div>
                                            </div>
                                            <div className="flex-shrink-0 ml-6">
                                                <button
                                                    type="button"
                                                    onClick={handleGraphToggle}
                                                    disabled={
                                                        buildingGraph ||
                                                        settings.graph_build_status ===
                                                            "building"
                                                    }
                                                    className={`px-4 py-2 rounded-md font-medium transition-all duration-200 ${
                                                        buildingGraph ||
                                                        settings.graph_build_status ===
                                                            "building"
                                                            ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                                                            : settings.enable_graph_enhanced_retrieval
                                                            ? settings.graph_build_status ===
                                                              "failed"
                                                                ? "bg-orange-600 text-white hover:bg-orange-700"
                                                                : "bg-red-600 text-white hover:bg-red-700"
                                                            : "bg-blue-600 text-white hover:bg-blue-700"
                                                    }`}
                                                >
                                                    {buildingGraph ||
                                                    settings.graph_build_status ===
                                                        "building"
                                                        ? "Building Graph..."
                                                        : settings.enable_graph_enhanced_retrieval
                                                        ? settings.graph_build_status ===
                                                          "failed"
                                                            ? "Retry Build"
                                                            : "Disable Graph Retrieval"
                                                        : "Enable Graph Retrieval"}
                                                </button>
                                            </div>
                                        </div>

                                        {/* Build Status Indicator */}
                                        {(settings.enable_graph_enhanced_retrieval ||
                                            graphBuildStatus ||
                                            graphBuildError) && (
                                            <div className="mt-4 p-3 bg-white rounded border">
                                                <div className="flex items-center">
                                                    <div className="flex-1">
                                                        <div className="text-sm font-medium text-gray-900">
                                                            Build Status:{" "}
                                                            {buildingGraph ||
                                                            settings.graph_build_status ===
                                                                "building" ? (
                                                                <span className="text-blue-600">
                                                                    ⏳
                                                                    Building...
                                                                </span>
                                                            ) : settings.graph_build_status ===
                                                              "built" ? (
                                                                <span className="text-green-600">
                                                                    ✓ Built
                                                                </span>
                                                            ) : settings.graph_build_status ===
                                                              "failed" ? (
                                                                <span className="text-red-600">
                                                                    ✗ Failed
                                                                </span>
                                                            ) : settings.graph_build_status ===
                                                              "outdated" ? (
                                                                <span className="text-orange-600">
                                                                    ⚠ Outdated
                                                                </span>
                                                            ) : (
                                                                <span className="text-gray-500">
                                                                    ○ Not Built
                                                                </span>
                                                            )}
                                                        </div>
                                                        <div className="text-xs text-gray-500 mt-1">
                                                            {graphBuildStatus && (
                                                                <div className="text-blue-600 font-medium">
                                                                    {
                                                                        graphBuildStatus
                                                                    }
                                                                </div>
                                                            )}
                                                            {graphBuildError && (
                                                                <div className="text-red-600 font-medium">
                                                                    {
                                                                        graphBuildError
                                                                    }
                                                                </div>
                                                            )}
                                                            {!graphBuildStatus &&
                                                                !graphBuildError && (
                                                                    <>
                                                                        {buildingGraph ||
                                                                            (settings.graph_build_status ===
                                                                                "building" &&
                                                                                "Building relationships between memories...")}
                                                                        {settings.graph_build_status ===
                                                                            "built" &&
                                                                            "Graph relationships are up to date"}
                                                                        {settings.graph_build_status ===
                                                                            "failed" &&
                                                                            "Graph build failed - check Neo4j connection"}
                                                                        {settings.graph_build_status ===
                                                                            "outdated" &&
                                                                            "Graph needs rebuilding for new memories"}
                                                                        {settings.graph_build_status ===
                                                                            "not_built" &&
                                                                            "Click 'Enable Graph Retrieval' to build the graph"}
                                                                    </>
                                                                )}
                                                        </div>
                                                        {buildingGraph && (
                                                            <div className="mt-2">
                                                                <div className="w-full bg-gray-200 rounded-full h-2">
                                                                    <div
                                                                        className="bg-blue-600 h-2 rounded-full animate-pulse"
                                                                        style={{
                                                                            width: "50%",
                                                                        }}
                                                                    ></div>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    {/* Information Panel */}
                                    <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
                                        <h4 className="text-sm font-medium text-blue-900 mb-2">
                                            🕸️ How Graph-Enhanced Retrieval
                                            Works
                                        </h4>
                                        <div className="text-sm text-blue-800 space-y-2">
                                            <p>
                                                <strong>Hybrid Search:</strong>{" "}
                                                Combines traditional vector
                                                similarity with relationship
                                                traversal
                                            </p>
                                            <p>
                                                <strong>
                                                    Automatic Building:
                                                </strong>{" "}
                                                Graph relationships are built
                                                incrementally as you add
                                                memories
                                            </p>
                                            <p>
                                                <strong>
                                                    Multiple Connections:
                                                </strong>{" "}
                                                Creates semantic, tag-based, and
                                                temporal relationships
                                            </p>
                                            <p>
                                                <strong>
                                                    Neo4j Dashboard:
                                                </strong>{" "}
                                                Use the Neo4j dashboard to
                                                explore relationship analytics
                                                and visualizations
                                            </p>
                                        </div>
                                    </div>

                                    {/* Neo4j Dashboard Link */}
                                    <div className="bg-gray-50 border border-gray-200 rounded-md p-4">
                                        <h4 className="text-sm font-medium text-gray-900 mb-2">
                                            📊 Graph Analytics
                                        </h4>
                                        <p className="text-sm text-gray-600 mb-3">
                                            For advanced graph analytics,
                                            relationship visualization, and
                                            cluster analysis, use the Neo4j
                                            dashboard.
                                        </p>
                                        <div className="flex items-center space-x-3">
                                            <a
                                                href="http://localhost:7474"
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                                            >
                                                🌐 Open Neo4j Dashboard
                                            </a>
                                            <span className="text-xs text-gray-500">
                                                Default: localhost:7474
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Status Messages */}
                        {error && (
                            <div className="bg-red-50 border border-red-200 rounded-md p-4">
                                <p className="text-red-800">{error}</p>
                            </div>
                        )}

                        {success && (
                            <div className="bg-green-50 border border-green-200 rounded-md p-4">
                                <p className="text-green-800">
                                    Settings updated successfully!
                                </p>
                            </div>
                        )}

                        {/* Submit Button */}
                        <div className="flex justify-end pt-6 border-t">
                            <button
                                type="submit"
                                disabled={saving}
                                className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {saving ? "Saving..." : "Save Settings"}
                            </button>
                        </div>
                    </form>
                </div>
            </main>
        </div>
    );
};

export default SettingsPage;
