import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getSettings, updateSettings } from "../services/api";
import { LLMSettings } from "../types";

type SettingsTab = "prompts" | "llm" | "embeddings" | "parameters" | "search";

const SettingsPage: React.FC = () => {
    const [settings, setSettings] = useState<LLMSettings | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [saving, setSaving] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<boolean>(false);
    const [activeTab, setActiveTab] = useState<SettingsTab>("prompts");
    const [showExtractionPreview, setShowExtractionPreview] = useState(false);
    const [showSearchPreview, setShowSearchPreview] = useState(false);

    // Refs for textareas
    const extractionPromptRef = useRef<HTMLTextAreaElement>(null);
    const searchPromptRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        const fetchSettings = async () => {
            try {
                const fetchedSettings = await getSettings();
                setSettings(fetchedSettings);
            } catch (err) {
                setError("Failed to fetch settings");
                console.error("Error fetching settings:", err);
            } finally {
                setLoading(false);
            }
        };

        fetchSettings();
    }, []);

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

    const tabs = [
        { id: "prompts" as SettingsTab, name: "Prompts", icon: "📝" },
        { id: "llm" as SettingsTab, name: "LLM Endpoints", icon: "🤖" },
        { id: "embeddings" as SettingsTab, name: "Embeddings", icon: "🔍" },
        { id: "parameters" as SettingsTab, name: "LLM Parameters", icon: "⚙️" },
        { id: "search" as SettingsTab, name: "Search Config", icon: "🎯" },
    ];

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
            <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="bg-white shadow rounded-lg">
                    {/* Header */}
                    <div className="px-6 py-4 border-b border-gray-200">
                        <div className="flex items-center justify-between">
                            <div>
                                <h1 className="text-2xl font-bold text-gray-900">
                                    Settings
                                </h1>
                                <p className="mt-1 text-sm text-gray-600">
                                    Configure your LLM endpoints, parameters,
                                    and prompts.
                                </p>
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
                                {/* Memory Extraction Prompt */}
                                <div>
                                    <div className="flex items-center justify-between mb-4">
                                        <div>
                                            <h3 className="text-lg font-medium text-gray-900">
                                                Memory Extraction Prompt
                                            </h3>
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
                                        onChange={(e) =>
                                            handleInputChange(
                                                "memory_extraction_prompt",
                                                e.target.value
                                            )
                                        }
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
                                        <div>
                                            <h3 className="text-lg font-medium text-gray-900">
                                                Memory Search Prompt
                                            </h3>
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
                                    <h3 className="text-lg font-medium text-gray-900 mb-4">
                                        Semantic Connection Analysis Prompt
                                    </h3>
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
                                    <h3 className="text-lg font-medium text-gray-900 mb-4">
                                        Memory Summarization Prompt
                                    </h3>
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

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Model
                                            </label>
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
                                                placeholder="e.g., gpt-4, llama3"
                                            />
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

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                Model
                                            </label>
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
                                                placeholder="e.g., text-embedding-ada-002, nomic-embed-text"
                                            />
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
            </div>
        </div>
    );
};

export default SettingsPage;
