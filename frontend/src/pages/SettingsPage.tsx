import React, { useEffect, useState, useCallback, useRef } from "react";
import { getSettings, updateSettings, validateEndpoint, fetchModels } from "../services/api";
import PageHeader from "../components/PageHeader";
import Dropdown from "../components/Dropdown";
import { useSidebar } from "../contexts/SidebarContext";

type TabType = 'embeddings' | 'generation' | 'reranking' | 'prompts' | 'amem';

const SettingsPage: React.FC = () => {
    const { isSidebarOpen } = useSidebar();
    const [activeTab, setActiveTab] = useState<TabType>('embeddings');
    const [settings, setSettings] = useState<any>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [editedSettings, setEditedSettings] = useState<any>(null);
    const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [saving, setSaving] = useState<boolean>(false);

    // Endpoint validation state
    const [validatingEmbeddings, setValidatingEmbeddings] = useState<boolean>(false);
    const [validatingGeneration, setValidatingGeneration] = useState<boolean>(false);
    const [embeddingsValidation, setEmbeddingsValidation] = useState<{success: boolean; message: string} | null>(null);
    const [generationValidation, setGenerationValidation] = useState<{success: boolean; message: string} | null>(null);

    // Model fetching state
    const [fetchingEmbeddingsModels, setFetchingEmbeddingsModels] = useState<boolean>(false);
    const [fetchingGenerationModels, setFetchingGenerationModels] = useState<boolean>(false);
    const [embeddingsModels, setEmbeddingsModels] = useState<string[]>([]);
    const [generationModels, setGenerationModels] = useState<string[]>([]);

    // Debounce timers
    const embeddingsDebounceRef = useRef<NodeJS.Timeout | null>(null);
    const generationDebounceRef = useRef<NodeJS.Timeout | null>(null);

    // Show default prompts
    const [showDefaultExtraction, setShowDefaultExtraction] = useState<boolean>(false);
    const [showNoteConstruction, setShowNoteConstruction] = useState<boolean>(false);
    const [showLinkGeneration, setShowLinkGeneration] = useState<boolean>(false);
    const [showMemoryEvolution, setShowMemoryEvolution] = useState<boolean>(false);

    useEffect(() => {
        const fetchSettings = async () => {
            try {
                const response = await getSettings();
                setSettings(response.settings);
                setEditedSettings(response.settings);
            } catch (err) {
                setError("Failed to fetch settings");
                console.error("Error fetching settings:", err);
            } finally {
                setLoading(false);
            }
        };

        fetchSettings();
    }, []);

    const handleFieldChange = (field: string, value: any) => {
        setEditedSettings((prev: any) => ({ ...prev, [field]: value }));
        setSaveSuccess(null);
        setSaveError(null);
    };

    const handleSave = async () => {
        setSaving(true);
        setSaveSuccess(null);
        setSaveError(null);

        try {
            const response = await updateSettings(editedSettings);
            if (response.success) {
                setSettings(response.settings);
                setEditedSettings(response.settings);
                setSaveSuccess(`Settings saved successfully! ${response.message}`);
            } else {
                setSaveError(response.error || "Failed to save settings");
            }
        } catch (err: any) {
            setSaveError(err.response?.data?.error || err.message || "Failed to save settings");
        } finally {
            setSaving(false);
        }
    };

    const handleReset = () => {
        setEditedSettings(settings);
        setSaveSuccess(null);
        setSaveError(null);
    };

    // Handler for validating embeddings endpoint
    const handleValidateEmbeddings = useCallback(async () => {
        if (!editedSettings?.embeddings_endpoint_url) return;

        setValidatingEmbeddings(true);
        setEmbeddingsValidation(null);
        setEmbeddingsModels([]); // Clear models when validating

        try {
            const result = await validateEndpoint(
                editedSettings.embeddings_endpoint_url,
                editedSettings.embeddings_provider,
                editedSettings.embeddings_api_key
            );
            const validation = {
                success: result.success,
                message: result.success ? result.message! : result.error!
            };
            setEmbeddingsValidation(validation);

            // Auto-fetch models on successful validation
            if (validation.success) {
                setFetchingEmbeddingsModels(true);
                try {
                    const modelsResult = await fetchModels(
                        editedSettings.embeddings_endpoint_url,
                        editedSettings.embeddings_provider,
                        editedSettings.embeddings_api_key
                    );
                    if (modelsResult.success && modelsResult.models) {
                        setEmbeddingsModels(modelsResult.models);
                    }
                } catch (err) {
                    console.error('Failed to fetch models:', err);
                } finally {
                    setFetchingEmbeddingsModels(false);
                }
            }
        } catch (err: any) {
            setEmbeddingsValidation({
                success: false,
                message: err.response?.data?.error || err.message || 'Validation failed'
            });
        } finally {
            setValidatingEmbeddings(false);
        }
    }, [editedSettings?.embeddings_endpoint_url, editedSettings?.embeddings_provider, editedSettings?.embeddings_api_key]);

    // Handler for validating generation endpoint
    const handleValidateGeneration = useCallback(async () => {
        const endpointUrl = editedSettings?.generation_endpoint_url || editedSettings?.embeddings_endpoint_url;
        if (!endpointUrl) return;

        setValidatingGeneration(true);
        setGenerationValidation(null);
        setGenerationModels([]); // Clear models when validating

        try {
            const provider = editedSettings.generation_provider || editedSettings.embeddings_provider;
            const apiKey = editedSettings.generation_api_key || editedSettings.embeddings_api_key;

            const result = await validateEndpoint(endpointUrl, provider, apiKey);
            const validation = {
                success: result.success,
                message: result.success ? result.message! : result.error!
            };
            setGenerationValidation(validation);

            // Auto-fetch models on successful validation
            if (validation.success) {
                setFetchingGenerationModels(true);
                try {
                    const modelsResult = await fetchModels(endpointUrl, provider, apiKey);
                    if (modelsResult.success && modelsResult.models) {
                        setGenerationModels(modelsResult.models);
                    }
                } catch (err) {
                    console.error('Failed to fetch models:', err);
                } finally {
                    setFetchingGenerationModels(false);
                }
            }
        } catch (err: any) {
            setGenerationValidation({
                success: false,
                message: err.response?.data?.error || err.message || 'Validation failed'
            });
        } finally {
            setValidatingGeneration(false);
        }
    }, [editedSettings?.generation_endpoint_url, editedSettings?.embeddings_endpoint_url, editedSettings?.generation_provider, editedSettings?.embeddings_provider, editedSettings?.generation_api_key, editedSettings?.embeddings_api_key]);

    // Auto-validate embeddings endpoint when it changes (with debounce)
    useEffect(() => {
        if (embeddingsDebounceRef.current) {
            clearTimeout(embeddingsDebounceRef.current);
        }

        if (editedSettings?.embeddings_endpoint_url) {
            embeddingsDebounceRef.current = setTimeout(() => {
                handleValidateEmbeddings();
            }, 1000); // 1 second debounce
        }

        return () => {
            if (embeddingsDebounceRef.current) {
                clearTimeout(embeddingsDebounceRef.current);
            }
        };
    }, [editedSettings?.embeddings_endpoint_url, editedSettings?.embeddings_provider, editedSettings?.embeddings_api_key, handleValidateEmbeddings]);

    // Auto-validate generation endpoint when it changes (with debounce)
    useEffect(() => {
        if (generationDebounceRef.current) {
            clearTimeout(generationDebounceRef.current);
        }

        const endpointUrl = editedSettings?.generation_endpoint_url || editedSettings?.embeddings_endpoint_url;
        if (endpointUrl) {
            generationDebounceRef.current = setTimeout(() => {
                handleValidateGeneration();
            }, 1000); // 1 second debounce
        }

        return () => {
            if (generationDebounceRef.current) {
                clearTimeout(generationDebounceRef.current);
            }
        };
    }, [editedSettings?.generation_endpoint_url, editedSettings?.embeddings_endpoint_url, editedSettings?.generation_provider, editedSettings?.embeddings_provider, editedSettings?.generation_api_key, editedSettings?.embeddings_api_key, handleValidateGeneration]);

    const hasChanges = JSON.stringify(settings) !== JSON.stringify(editedSettings);

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
                <div className="text-center">
                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 dark:border-gray-100"></div>
                    <p className="mt-2 text-gray-600 dark:text-gray-400">Loading settings...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6">
                    <p className="text-red-800 dark:text-red-300">{error}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
            <PageHeader
                title="Settings"
                subtitle="Configure LLM providers, models, and parameters for embeddings and text generation"
                badge={{ text: "Configuration", color: "gray" }}
            />

            <div className={`transition-all duration-300 ${isSidebarOpen ? 'ml-60' : 'ml-0'}`}>
            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Save Status Messages */}
                {saveSuccess && (
                    <div className="mb-6 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
                        <p className="text-green-800 dark:text-green-300">{saveSuccess}</p>
                    </div>
                )}

                {saveError && (
                    <div className="mb-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                        <p className="text-red-800 dark:text-red-300">{saveError}</p>
                    </div>
                )}

                {/* Information Banner */}
                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6 mb-8">
                    <h2 className="text-lg font-semibold text-blue-900 dark:text-blue-100 mb-2">
                        ⚙️ Editable Configuration
                    </h2>
                    <p className="text-blue-800 dark:text-blue-200">
                        Settings are stored in the database and can be edited directly from this page.
                        Changes take effect immediately without requiring a restart.
                    </p>
                </div>

                {/* Tabs */}
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md">
                    {/* Tab Navigation */}
                    <div className="border-b border-gray-200 dark:border-gray-700">
                        {/* Mobile: Dropdown */}
                        <div className="sm:hidden px-4 py-3">
                            <label htmlFor="tab-select" className="sr-only">
                                Select configuration section
                            </label>
                            <select
                                id="tab-select"
                                value={activeTab}
                                onChange={(e) => setActiveTab(e.target.value as TabType)}
                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm font-medium"
                            >
                                <option value="embeddings">Embeddings Configuration</option>
                                <option value="generation">Generation Configuration</option>
                                <option value="reranking">Reranking Configuration</option>
                                <option value="prompts">Prompts Configuration</option>
                                <option value="amem">A-MEM & Advanced</option>
                            </select>
                        </div>

                        {/* Desktop: Tab Buttons */}
                        <nav className="hidden sm:flex -mb-px">
                            <button
                                onClick={() => setActiveTab('embeddings')}
                                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                                    activeTab === 'embeddings'
                                        ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                                        : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
                                }`}
                            >
                                Embeddings
                            </button>
                            <button
                                onClick={() => setActiveTab('generation')}
                                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                                    activeTab === 'generation'
                                        ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                                        : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
                                }`}
                            >
                                Generation
                            </button>
                            <button
                                onClick={() => setActiveTab('reranking')}
                                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                                    activeTab === 'reranking'
                                        ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                                        : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
                                }`}
                            >
                                Reranking
                            </button>
                            <button
                                onClick={() => setActiveTab('prompts')}
                                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                                    activeTab === 'prompts'
                                        ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                                        : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
                                }`}
                            >
                                Prompts
                            </button>
                            <button
                                onClick={() => setActiveTab('amem')}
                                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                                    activeTab === 'amem'
                                        ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                                        : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
                                }`}
                            >
                                A-MEM
                            </button>
                        </nav>
                    </div>

                    {/* Tab Content */}
                    <div className="p-4 sm:p-6">
                        {/* Embeddings Tab */}
                        {activeTab === 'embeddings' && (
                            <div className="space-y-6">
                                <div>
                                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
                                        Embeddings Configuration
                                    </h3>
                                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
                                        Configuration for generating embeddings used in semantic search and vector storage.
                                    </p>
                                </div>

                                {/* Provider */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Provider
                                    </label>
                                    <Dropdown
                                        value={editedSettings.embeddings_provider}
                                        options={[
                                            { value: 'ollama', label: 'Ollama' },
                                            { value: 'openai', label: 'OpenAI' },
                                            { value: 'openai_compatible', label: 'OpenAI Compatible' }
                                        ]}
                                        onChange={(value) => handleFieldChange('embeddings_provider', value)}
                                    />
                                </div>

                                {/* Endpoint URL */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Endpoint URL
                                    </label>
                                    <input
                                        type="text"
                                        value={editedSettings.embeddings_endpoint_url}
                                        onChange={(e) => handleFieldChange('embeddings_endpoint_url', e.target.value)}
                                        placeholder="http://localhost:11434"
                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    {validatingEmbeddings && (
                                        <p className="mt-1 text-sm text-blue-600 dark:text-blue-400">
                                            ⏳ Validating endpoint...
                                        </p>
                                    )}
                                    {!validatingEmbeddings && embeddingsValidation && (
                                        <p className={`mt-1 text-sm ${embeddingsValidation.success ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                                            {embeddingsValidation.success ? '✓ ' : '✗ '}{embeddingsValidation.message}
                                        </p>
                                    )}
                                    {fetchingEmbeddingsModels && (
                                        <p className="mt-1 text-sm text-blue-600 dark:text-blue-400">
                                            ⏳ Fetching available models...
                                        </p>
                                    )}
                                </div>

                                {/* Model */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Model
                                    </label>
                                    {embeddingsModels.length > 0 ? (
                                        <Dropdown
                                            value={editedSettings.embeddings_model}
                                            options={embeddingsModels.map(model => ({ value: model, label: model }))}
                                            onChange={(value) => handleFieldChange('embeddings_model', value)}
                                        />
                                    ) : (
                                        <input
                                            type="text"
                                            value={editedSettings.embeddings_model}
                                            onChange={(e) => handleFieldChange('embeddings_model', e.target.value)}
                                            placeholder="mxbai-embed-large"
                                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        />
                                    )}
                                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                        Models are automatically fetched when the endpoint is validated
                                    </p>
                                </div>

                                {/* API Key */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        API Key (Optional)
                                    </label>
                                    <input
                                        type="password"
                                        value={editedSettings.embeddings_api_key}
                                        onChange={(e) => handleFieldChange('embeddings_api_key', e.target.value)}
                                        placeholder="••••••••"
                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                        Leave empty for providers that don't require authentication
                                    </p>
                                </div>

                                {/* Timeout */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Timeout (seconds)
                                    </label>
                                    <input
                                        type="number"
                                        min="1"
                                        max="600"
                                        value={editedSettings.embeddings_timeout}
                                        onChange={(e) => handleFieldChange('embeddings_timeout', parseInt(e.target.value))}
                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                            </div>
                        )}

                        {/* Generation Tab */}
                        {activeTab === 'generation' && (
                            <div className="space-y-6">
                                <div>
                                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
                                        Generation Configuration
                                    </h3>
                                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
                                        Separate configuration for text generation (atomic note extraction, relationship building).
                                        Leave fields blank to use embeddings configuration.
                                    </p>
                                </div>

                                {/* Provider */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Provider
                                    </label>
                                    <Dropdown
                                        value={editedSettings.generation_provider || ''}
                                        options={[
                                            { value: '', label: 'Same as Embeddings' },
                                            { value: 'ollama', label: 'Ollama' },
                                            { value: 'openai', label: 'OpenAI' },
                                            { value: 'openai_compatible', label: 'OpenAI Compatible' }
                                        ]}
                                        onChange={(value) => handleFieldChange('generation_provider', value)}
                                    />
                                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                        Leave as "Same as Embeddings" to inherit provider settings from the Embeddings tab
                                    </p>
                                </div>

                                {/* Endpoint URL */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Endpoint URL
                                    </label>
                                    <input
                                        type="text"
                                        value={editedSettings.generation_endpoint_url || ''}
                                        onChange={(e) => handleFieldChange('generation_endpoint_url', e.target.value)}
                                        placeholder="(use embeddings endpoint)"
                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    {validatingGeneration && (
                                        <p className="mt-1 text-sm text-blue-600 dark:text-blue-400">
                                            ⏳ Validating endpoint...
                                        </p>
                                    )}
                                    {!validatingGeneration && generationValidation && (
                                        <p className={`mt-1 text-sm ${generationValidation.success ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                                            {generationValidation.success ? '✓ ' : '✗ '}{generationValidation.message}
                                        </p>
                                    )}
                                    {fetchingGenerationModels && (
                                        <p className="mt-1 text-sm text-blue-600 dark:text-blue-400">
                                            ⏳ Fetching available models...
                                        </p>
                                    )}
                                </div>

                                {/* Model */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Model
                                    </label>
                                    {generationModels.length > 0 ? (
                                        <Dropdown
                                            value={editedSettings.generation_model || ''}
                                            options={generationModels.map(model => ({ value: model, label: model }))}
                                            onChange={(value) => handleFieldChange('generation_model', value)}
                                        />
                                    ) : (
                                        <input
                                            type="text"
                                            value={editedSettings.generation_model || ''}
                                            onChange={(e) => handleFieldChange('generation_model', e.target.value)}
                                            placeholder="(use embeddings model)"
                                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        />
                                    )}
                                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                        Models are automatically fetched when the endpoint is validated
                                    </p>
                                </div>

                                {/* API Key */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        API Key
                                    </label>
                                    <input
                                        type="password"
                                        value={editedSettings.generation_api_key || ''}
                                        onChange={(e) => handleFieldChange('generation_api_key', e.target.value)}
                                        placeholder="(use embeddings API key)"
                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                {/* Temperature */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Temperature (0.0 - 1.0)
                                    </label>
                                    <input
                                        type="number"
                                        min="0"
                                        max="1"
                                        step="0.1"
                                        value={editedSettings.generation_temperature}
                                        onChange={(e) => handleFieldChange('generation_temperature', parseFloat(e.target.value))}
                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                        Higher values = more creative, lower values = more focused
                                    </p>
                                </div>

                                {/* Max Tokens */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Max Tokens
                                    </label>
                                    <input
                                        type="number"
                                        min="1"
                                        max="100000"
                                        value={editedSettings.generation_max_tokens}
                                        onChange={(e) => handleFieldChange('generation_max_tokens', parseInt(e.target.value))}
                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                {/* Timeout */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Timeout (seconds)
                                    </label>
                                    <input
                                        type="number"
                                        min="1"
                                        max="600"
                                        value={editedSettings.generation_timeout}
                                        onChange={(e) => handleFieldChange('generation_timeout', parseInt(e.target.value))}
                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                {/* Top-P */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Top-P (0.0 - 1.0)
                                    </label>
                                    <input
                                        type="number"
                                        min="0"
                                        max="1"
                                        step="0.1"
                                        value={editedSettings.generation_top_p ?? 0.8}
                                        onChange={(e) => handleFieldChange('generation_top_p', parseFloat(e.target.value))}
                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                        Nucleus sampling - only tokens with cumulative probability up to this value are considered
                                    </p>
                                </div>

                                {/* Top-K */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Top-K (0 = disabled)
                                    </label>
                                    <input
                                        type="number"
                                        min="0"
                                        max="1000"
                                        value={editedSettings.generation_top_k ?? 20}
                                        onChange={(e) => handleFieldChange('generation_top_k', parseInt(e.target.value))}
                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                        Limits sampling to top K most likely tokens (0 = disabled)
                                    </p>
                                </div>

                                {/* Min-P */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Min-P (0.0 - 1.0)
                                    </label>
                                    <input
                                        type="number"
                                        min="0"
                                        max="1"
                                        step="0.05"
                                        value={editedSettings.generation_min_p ?? 0.0}
                                        onChange={(e) => handleFieldChange('generation_min_p', parseFloat(e.target.value))}
                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                        Minimum probability threshold relative to most likely token (0 = disabled)
                                    </p>
                                </div>
                            </div>
                        )}

                        {/* Reranking Tab */}
                        {activeTab === 'reranking' && (
                            <div className="space-y-6">
                                <div>
                                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
                                        Reranking Configuration
                                    </h3>
                                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
                                        Configure cross-encoder reranking to improve search precision and recall.
                                        Reranking retrieves more candidates from vector search, then uses a more accurate model to rerank them.
                                    </p>
                                </div>

                                {/* Enable Reranking */}
                                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                                    <div className="flex items-start gap-3">
                                        <input
                                            type="checkbox"
                                            id="enable_reranking"
                                            checked={editedSettings.enable_reranking || false}
                                            onChange={(e) => handleFieldChange('enable_reranking', e.target.checked)}
                                            className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                                        />
                                        <div className="flex-1">
                                            <label htmlFor="enable_reranking" className="block text-sm font-medium text-blue-900 dark:text-blue-100 cursor-pointer">
                                                Enable Reranking
                                            </label>
                                            <p className="text-sm text-blue-800 dark:text-blue-200 mt-1">
                                                Improve search quality by reranking initial results with a more accurate model.
                                                Expected improvement: +5-10% precision, +8-15% recall.
                                            </p>
                                        </div>
                                    </div>
                                </div>

                                {/* Provider */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Provider
                                    </label>
                                    <Dropdown
                                        value={editedSettings.reranking_provider || 'ollama'}
                                        options={[
                                            { value: 'remote', label: 'Remote Server (GPU recommended)' },
                                            { value: 'ollama', label: 'Ollama (LLM-based)' },
                                            { value: 'sentence_transformers', label: 'Sentence Transformers (Local)' }
                                        ]}
                                        onChange={(value) => handleFieldChange('reranking_provider', value)}
                                    />
                                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                        {editedSettings.reranking_provider === 'remote' &&
                                            '🚀 Best performance: Connect to GPU server running reranking endpoint'
                                        }
                                        {editedSettings.reranking_provider === 'ollama' &&
                                            '🐢 Good quality, slower: Uses LLM for relevance scoring'
                                        }
                                        {editedSettings.reranking_provider === 'sentence_transformers' &&
                                            '⚡ Fast with GPU, slow with CPU: Loads model locally'
                                        }
                                    </p>
                                </div>

                                {/* Remote Server Settings */}
                                {editedSettings.reranking_provider === 'remote' && (
                                    <div className="space-y-4 pl-4 border-l-2 border-blue-500">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                                Endpoint URL
                                            </label>
                                            <input
                                                type="text"
                                                value={editedSettings.reranking_endpoint_url || ''}
                                                onChange={(e) => handleFieldChange('reranking_endpoint_url', e.target.value)}
                                                placeholder="http://your-gpu-server:8081"
                                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                                URL of your reranking server (TEI or custom FastAPI)
                                            </p>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                                Model Name
                                            </label>
                                            <input
                                                type="text"
                                                value={editedSettings.reranking_model_name || 'BAAI/bge-reranker-base'}
                                                onChange={(e) => handleFieldChange('reranking_model_name', e.target.value)}
                                                placeholder="BAAI/bge-reranker-base"
                                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                                Model reference (display only, actual model loaded on server)
                                            </p>
                                        </div>
                                    </div>
                                )}

                                {/* Ollama Settings */}
                                {editedSettings.reranking_provider === 'ollama' && (
                                    <div className="space-y-4 pl-4 border-l-2 border-purple-500">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                                Ollama Base URL
                                            </label>
                                            <input
                                                type="text"
                                                value={editedSettings.ollama_reranking_base_url || 'http://host.docker.internal:11434'}
                                                onChange={(e) => handleFieldChange('ollama_reranking_base_url', e.target.value)}
                                                placeholder="http://host.docker.internal:11434"
                                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                                Ollama Model
                                            </label>
                                            <input
                                                type="text"
                                                value={editedSettings.ollama_reranking_model || 'llama3.2:3b'}
                                                onChange={(e) => handleFieldChange('ollama_reranking_model', e.target.value)}
                                                placeholder="llama3.2:3b"
                                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                                Recommended: llama3.2:3b, qwen2.5:3b, or gemma2:2b
                                            </p>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                                Temperature
                                            </label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                min="0"
                                                max="1"
                                                value={editedSettings.ollama_reranking_temperature ?? 0.0}
                                                onChange={(e) => handleFieldChange('ollama_reranking_temperature', parseFloat(e.target.value))}
                                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                                0.0 = deterministic scoring (recommended)
                                            </p>
                                        </div>
                                    </div>
                                )}

                                {/* Sentence Transformers Settings */}
                                {editedSettings.reranking_provider === 'sentence_transformers' && (
                                    <div className="space-y-4 pl-4 border-l-2 border-green-500">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                                Model Name
                                            </label>
                                            <input
                                                type="text"
                                                value={editedSettings.reranking_model_name || 'BAAI/bge-reranker-base'}
                                                onChange={(e) => handleFieldChange('reranking_model_name', e.target.value)}
                                                placeholder="BAAI/bge-reranker-base"
                                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                                Recommended: BAAI/bge-reranker-base (278M params, balanced) or cross-encoder/ms-marco-MiniLM-L-6-v2 (faster on CPU)
                                            </p>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                                Device
                                            </label>
                                            <Dropdown
                                                value={editedSettings.reranking_device || 'cpu'}
                                                options={[
                                                    { value: 'auto', label: 'Auto-detect' },
                                                    { value: 'cpu', label: 'CPU' },
                                                    { value: 'cuda', label: 'CUDA (GPU)' }
                                                ]}
                                                onChange={(value) => handleFieldChange('reranking_device', value)}
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                                Batch Size
                                            </label>
                                            <input
                                                type="number"
                                                min="1"
                                                max="64"
                                                value={editedSettings.reranking_batch_size || 16}
                                                onChange={(e) => handleFieldChange('reranking_batch_size', parseInt(e.target.value))}
                                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                                Lower = less memory, Higher = faster (GPU only)
                                            </p>
                                        </div>
                                    </div>
                                )}

                                {/* Performance Settings */}
                                <div>
                                    <h4 className="text-md font-semibold text-gray-900 dark:text-gray-100 mb-3">
                                        Performance Settings
                                    </h4>

                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                            Candidate Multiplier
                                        </label>
                                        <input
                                            type="number"
                                            min="2"
                                            max="10"
                                            value={editedSettings.reranking_candidate_multiplier || 3}
                                            onChange={(e) => handleFieldChange('reranking_candidate_multiplier', parseInt(e.target.value))}
                                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        />
                                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                            Retrieve N× more candidates before reranking. Example: 3 means retrieve 30 candidates to rerank top 10.
                                            Higher = better recall but slower. Recommended: 3-5.
                                        </p>
                                    </div>
                                </div>

                                {/* Information Box */}
                                <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                                    <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">
                                        📊 Expected Improvements
                                    </h4>
                                    <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                                        <li>• Precision@10: +5-10% improvement</li>
                                        <li>• Recall@10: +8-15% improvement</li>
                                        <li>• Latency: +50-200ms per query</li>
                                    </ul>
                                    <p className="text-xs text-gray-500 dark:text-gray-500 mt-3">
                                        💡 Tip: Use "remote" provider with GPU server for best performance, or "ollama" for quick setup without additional infrastructure.
                                    </p>
                                </div>
                            </div>
                        )}

                        {/* Prompts Tab */}
                        {activeTab === 'prompts' && (
                            <div className="space-y-6">
                                <div>
                                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
                                        Prompt Customization
                                    </h3>
                                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
                                        Customize the prompts used for atomic note extraction and relationship building.
                                        Leave empty to use default prompts. Prompts should include template variables.
                                    </p>
                                </div>

                                {/* Extraction Prompt */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Extraction Prompt
                                    </label>
                                    <textarea
                                        value={editedSettings.extraction_prompt || ''}
                                        onChange={(e) => handleFieldChange('extraction_prompt', e.target.value)}
                                        placeholder="Leave empty to use default extraction prompt"
                                        rows={12}
                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                                    />
                                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                        Required template variables: {'{user_message}'}, {'{assistant_message}'}
                                    </p>
                                    <button
                                        type="button"
                                        onClick={() => setShowDefaultExtraction(!showDefaultExtraction)}
                                        className="mt-2 text-sm text-blue-600 hover:text-blue-800"
                                    >
                                        {showDefaultExtraction ? '▼ Hide' : '▶ Show'} Default Extraction Prompt
                                    </button>
                                    {showDefaultExtraction && (
                                        <div className="mt-3 p-4 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-md">
                                            <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Default Extraction Prompt:</p>
                                            <pre className="text-xs text-gray-800 dark:text-gray-200 whitespace-pre-wrap font-mono">
{`Extract atomic facts from this conversation turn.

**Conversation:**
User: {user_message}
Assistant: {assistant_message}

**Instructions:**
Extract individual, atomic facts about the user. Each fact should be:
1. A single, granular piece of information
2. Self-contained and understandable on its own
3. About the user's preferences, skills, interests, or personal information

**Format your response as JSON:**
\`\`\`json
{
  "notes": [
    {
      "content": "single atomic fact",
      "type": "category:subcategory",
      "context": "brief context about when/why mentioned",
      "confidence": 0.95,
      "tags": ["tag1", "tag2"]
    }
  ]
}
\`\`\`

**Note Types:**
- preference:ui - UI/UX preferences
- preference:editor - Editor/IDE preferences
- preference:tool - Tool preferences
- skill:programming - Programming skills
- skill:language - Language skills
- interest:topic - Topic interests
- interest:hobby - Hobbies and activities
- personal:location - Location information
- personal:background - Background information
- goal:career - Career goals
- goal:learning - Learning goals

**Guidelines:**
- Only extract facts explicitly stated or strongly implied
- Do NOT extract assistant responses unless they reveal user information
- Break compound statements into multiple atomic facts
- Set confidence lower (0.6-0.8) for implied facts
- Set confidence higher (0.9-1.0) for explicit statements

**Examples:**

User: "I prefer dark mode and use vim keybindings in VSCode"
\`\`\`json
{
  "notes": [
    {
      "content": "prefers dark mode",
      "type": "preference:ui",
      "context": "mentioned while discussing editor preferences",
      "confidence": 1.0,
      "tags": ["ui", "dark-mode"]
    },
    {
      "content": "uses vim keybindings",
      "type": "preference:editor",
      "context": "mentioned while discussing editor preferences",
      "confidence": 1.0,
      "tags": ["vim", "keybindings"]
    },
    {
      "content": "primary editor is VSCode",
      "type": "preference:tool",
      "context": "mentioned while discussing editor preferences",
      "confidence": 1.0,
      "tags": ["vscode", "editor"]
    }
  ]
}
\`\`\`

Now extract facts from the conversation above:`}
                                            </pre>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* A-MEM Tab */}
                        {activeTab === 'amem' && (
                            <div className="space-y-8">
                                {/* Header */}
                                <div>
                                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
                                        A-MEM Configuration & Advanced Settings
                                    </h3>
                                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
                                        View the A-MEM prompts used for note construction, link generation, and memory evolution.
                                        Adjust advanced parameters to fine-tune A-MEM behavior.
                                    </p>
                                </div>

                                {/* A-MEM Prompts - Read Only */}
                                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6">
                                    <h4 className="text-md font-semibold text-blue-900 dark:text-blue-100 mb-3">
                                        A-MEM Prompts (Read-Only)
                                    </h4>
                                    <p className="text-sm text-blue-800 dark:text-blue-200 mb-4">
                                        These prompts are from the A-MEM paper (NeurIPS 2025, Appendix B) and cannot be edited.
                                        They control how Mnemosyne enriches notes, generates links, and evolves memories.
                                    </p>

                                    {/* Note Construction Prompt */}
                                    <div className="mb-4">
                                        <button
                                            type="button"
                                            onClick={() => setShowNoteConstruction(!showNoteConstruction)}
                                            className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
                                        >
                                            {showNoteConstruction ? '▼ Hide' : '▶ Show'} Note Construction Prompt (Phase 1)
                                        </button>
                                        {showNoteConstruction && (
                                            <div className="mt-3 p-4 bg-white dark:bg-gray-800 border border-blue-200 dark:border-blue-700 rounded-md">
                                                <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">
                                                    Phase 1: Note Enrichment (Keywords, Context, Tags)
                                                </p>
                                                <pre className="text-xs text-gray-800 dark:text-gray-200 whitespace-pre-wrap font-mono overflow-x-auto">
{`Generate a structured analysis of the following content by:
1. Identifying the most salient keywords (focus on nouns, verbs, and key concepts)
2. Extracting core themes and contextual elements
3. Creating relevant categorical tags

Format the response as a JSON object:
{
  "keywords": [
    // several specific, distinct keywords that capture key concepts and terminology
    // Order from most to least important
    // Don't include keywords that are the name of the speaker or time
    // At least three keywords, but don't be too redundant.
  ],
  "context": // one sentence summarizing:
             // - Main topic/domain
             // - Key arguments/points
             // - Intended audience/purpose,
  "tags": [
    // several broad categories/themes for classification
    // Include domain, format, and type tags
    // At least three tags, but don't be too redundant.
  ]
}

Content for analysis:
{content}

Timestamp: {timestamp}`}
                                                </pre>
                                            </div>
                                        )}
                                    </div>

                                    {/* Link Generation Prompt */}
                                    <div className="mb-4">
                                        <button
                                            type="button"
                                            onClick={() => setShowLinkGeneration(!showLinkGeneration)}
                                            className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
                                        >
                                            {showLinkGeneration ? '▼ Hide' : '▶ Show'} Link Generation Prompt (Phase 3)
                                        </button>
                                        {showLinkGeneration && (
                                            <div className="mt-3 p-4 bg-white dark:bg-gray-800 border border-blue-200 dark:border-blue-700 rounded-md">
                                                <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">
                                                    Phase 3: Link Generation (Relationship Analysis)
                                                </p>
                                                <pre className="text-xs text-gray-800 dark:text-gray-200 whitespace-pre-wrap font-mono overflow-x-auto">
{`You are an AI memory evolution agent responsible for managing and evolving a knowledge base.

Analyze the new memory note according to keywords and context, also with their several nearest neighbors memory.

The new memory:
Context: {new_context}
Content: {new_content}
Keywords: {new_keywords}

The nearest neighbors memories:
{nearest_neighbors}

Based on this information, determine:
Should this memory be evolved? Consider its relationships with other memories.

Return your decision in JSON format:
{
  "should_link": true/false,
  "links": [
    {
      "target_note_id": "uuid",
      "relationship_type": "string",
      "strength": 0.0-1.0,
      "rationale": "why this link makes sense"
    }
  ]
}`}
                                                </pre>
                                            </div>
                                        )}
                                    </div>

                                    {/* Memory Evolution Prompt */}
                                    <div>
                                        <button
                                            type="button"
                                            onClick={() => setShowMemoryEvolution(!showMemoryEvolution)}
                                            className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
                                        >
                                            {showMemoryEvolution ? '▼ Hide' : '▶ Show'} Memory Evolution Prompt (Phase 4)
                                        </button>
                                        {showMemoryEvolution && (
                                            <div className="mt-3 p-4 bg-white dark:bg-gray-800 border border-blue-200 dark:border-blue-700 rounded-md">
                                                <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">
                                                    Phase 4: Memory Evolution (Neighbor Updates)
                                                </p>
                                                <pre className="text-xs text-gray-800 dark:text-gray-200 whitespace-pre-wrap font-mono overflow-x-auto">
{`You are an AI memory evolution agent responsible for managing and evolving a knowledge base.

Analyze the new memory note according to keywords and context, also with their several nearest neighbors memory.

Make decisions about its evolution.

The new memory:
Context: {new_context}
Content: {new_content}
Keywords: {new_keywords}

The nearest neighbors memories:
{nearest_neighbors}

Based on this information, determine:
1. What specific actions should be taken (strengthen, update_neighbor)?
1.1 If choose to strengthen the connection, which memory should it be connected to? Can you give the updated tags of this memory?
1.2 If choose to update neighbor, you can update the context and tags of these memories based on the understanding of these memories.

Tags should be determined by the content of these characteristic of these memories, which can be used to retrieve them later and categorize them.

All the above information should be returned in a list format according to the sequence: [[new_memory],[neighbor_memory_1],...[neighbor_memory_n]]

Return your decision in JSON format:
{
  "should_evolve": true/false,
  "actions": ["strengthen", "merge", "prune"],
  "suggested_connections": ["neighbor_memory_ids"],
  "tags_to_update": ["tag_1",...,"tag_n"],
  "new_context_neighborhood": ["new context",...,"new context"],
  "new_tags_neighborhood": [["tag_1",...,"tag_n"],...["tag_1",...,"tag_n"]]
}`}
                                                </pre>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Advanced Settings */}
                                <div>
                                    <h4 className="text-md font-semibold text-gray-900 dark:text-gray-100 mb-4">
                                        Advanced A-MEM Parameters
                                    </h4>
                                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
                                        Fine-tune how A-MEM processes your memories. Lower temperature = more focused/deterministic,
                                        higher temperature = more creative/varied responses.
                                    </p>

                                    <div className="space-y-6">
                                        {/* Note Enrichment Settings */}
                                        <div className="bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600 rounded-lg p-4">
                                            <h5 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
                                                Phase 1: Note Enrichment
                                            </h5>
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                <div>
                                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                                        Temperature (0.0 - 1.0)
                                                    </label>
                                                    <input
                                                        type="number"
                                                        min="0"
                                                        max="1"
                                                        step="0.1"
                                                        value={editedSettings?.amem_enrichment_temperature ?? 0.3}
                                                        onChange={(e) => handleFieldChange('amem_enrichment_temperature', parseFloat(e.target.value))}
                                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                    />
                                                </div>
                                                <div>
                                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                                        Max Tokens
                                                    </label>
                                                    <input
                                                        type="number"
                                                        min="50"
                                                        max="2000"
                                                        value={editedSettings?.amem_enrichment_max_tokens ?? 300}
                                                        onChange={(e) => handleFieldChange('amem_enrichment_max_tokens', parseInt(e.target.value))}
                                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                    />
                                                </div>
                                            </div>
                                        </div>

                                        {/* Link Generation Settings */}
                                        <div className="bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600 rounded-lg p-4">
                                            <h5 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
                                                Phase 3: Link Generation
                                            </h5>
                                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                                <div>
                                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                                        Temperature (0.0 - 1.0)
                                                    </label>
                                                    <input
                                                        type="number"
                                                        min="0"
                                                        max="1"
                                                        step="0.1"
                                                        value={editedSettings?.amem_link_generation_temperature ?? 0.3}
                                                        onChange={(e) => handleFieldChange('amem_link_generation_temperature', parseFloat(e.target.value))}
                                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                    />
                                                </div>
                                                <div>
                                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                                        Max Tokens
                                                    </label>
                                                    <input
                                                        type="number"
                                                        min="50"
                                                        max="2000"
                                                        value={editedSettings?.amem_link_generation_max_tokens ?? 500}
                                                        onChange={(e) => handleFieldChange('amem_link_generation_max_tokens', parseInt(e.target.value))}
                                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                    />
                                                </div>
                                                <div>
                                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                                        k (Nearest Neighbors)
                                                    </label>
                                                    <input
                                                        type="number"
                                                        min="1"
                                                        max="50"
                                                        value={editedSettings?.amem_link_generation_k ?? 10}
                                                        onChange={(e) => handleFieldChange('amem_link_generation_k', parseInt(e.target.value))}
                                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                    />
                                                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                                        Number of similar notes to consider
                                                    </p>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Memory Evolution Settings */}
                                        <div className="bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600 rounded-lg p-4">
                                            <h5 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
                                                Phase 4: Memory Evolution
                                            </h5>
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                <div>
                                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                                        Temperature (0.0 - 1.0)
                                                    </label>
                                                    <input
                                                        type="number"
                                                        min="0"
                                                        max="1"
                                                        step="0.1"
                                                        value={editedSettings?.amem_evolution_temperature ?? 0.3}
                                                        onChange={(e) => handleFieldChange('amem_evolution_temperature', parseFloat(e.target.value))}
                                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                    />
                                                </div>
                                                <div>
                                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                                        Max Tokens
                                                    </label>
                                                    <input
                                                        type="number"
                                                        min="50"
                                                        max="2000"
                                                        value={editedSettings?.amem_evolution_max_tokens ?? 800}
                                                        onChange={(e) => handleFieldChange('amem_evolution_max_tokens', parseInt(e.target.value))}
                                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Sticky Action Bar */}
                    <div className="sticky bottom-0 left-0 right-0 px-4 sm:px-6 py-3 sm:py-4 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 shadow-lg z-10">
                        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
                            {/* Unsaved changes indicator */}
                            {hasChanges && (
                                <div className="flex items-center gap-2 text-sm text-amber-700 dark:text-amber-400">
                                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                    </svg>
                                    <span className="font-medium">You have unsaved changes</span>
                                </div>
                            )}

                            {/* Action buttons */}
                            <div className="flex gap-2 sm:gap-3 sm:ml-auto">
                                <button
                                    onClick={handleReset}
                                    disabled={!hasChanges || saving}
                                    className="flex-1 sm:flex-initial px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
                                >
                                    Reset
                                </button>
                                <button
                                    onClick={handleSave}
                                    disabled={!hasChanges || saving}
                                    className="flex-1 sm:flex-initial px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
                                >
                                    {saving ? 'Saving...' : 'Save Changes'}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </main>
            </div>
        </div>
    );
};

export default SettingsPage;
