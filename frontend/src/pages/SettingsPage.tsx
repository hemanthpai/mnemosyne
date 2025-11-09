import React, { useEffect, useState, useCallback, useRef } from "react";
import { getSettings, updateSettings, validateEndpoint, fetchModels } from "../services/api";
import PageHeader from "../components/PageHeader";
import Dropdown from "../components/Dropdown";

type TabType = 'embeddings' | 'generation' | 'prompts';

const SettingsPage: React.FC = () => {
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
    const [showDefaultRelationship, setShowDefaultRelationship] = useState<boolean>(false);

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
                badge={{ text: "Configuration", color: "gray" }}
            />

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
                                <option value="prompts">Prompts Configuration</option>
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
                                onClick={() => setActiveTab('prompts')}
                                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                                    activeTab === 'prompts'
                                        ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                                        : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
                                }`}
                            >
                                Prompts
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

                                {/* Relationship Prompt */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Relationship Prompt
                                    </label>
                                    <textarea
                                        value={editedSettings.relationship_prompt || ''}
                                        onChange={(e) => handleFieldChange('relationship_prompt', e.target.value)}
                                        placeholder="Leave empty to use default relationship prompt"
                                        rows={12}
                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                                    />
                                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                        Required template variables: {'{new_note_content}'}, {'{new_note_type}'}, {'{new_note_context}'}, {'{existing_notes}'}
                                    </p>
                                    <button
                                        type="button"
                                        onClick={() => setShowDefaultRelationship(!showDefaultRelationship)}
                                        className="mt-2 text-sm text-blue-600 hover:text-blue-800"
                                    >
                                        {showDefaultRelationship ? '▼ Hide' : '▶ Show'} Default Relationship Prompt
                                    </button>
                                    {showDefaultRelationship && (
                                        <div className="mt-3 p-4 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-md">
                                            <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Default Relationship Prompt:</p>
                                            <pre className="text-xs text-gray-800 dark:text-gray-200 whitespace-pre-wrap font-mono">
{`Analyze relationships between atomic notes.

**New Note:**
Content: {new_note_content}
Type: {new_note_type}
Context: {new_note_context}

**Existing Notes:**
{existing_notes}

**Instructions:**
Identify relationships between the new note and existing notes. For each relationship found:
1. Determine the relationship type
2. Assess the strength (0.0-1.0, where 1.0 is strongest)

**Relationship Types:**
- **related_to**: General thematic connection (e.g., both about Python, both preferences)
- **contradicts**: Direct contradiction (e.g., "prefers dark mode" vs "prefers light mode")
- **refines**: The new note adds detail/nuance to an existing note
- **context_for**: The new note provides context for understanding an existing note
- **follows_from**: The new note is a logical consequence of an existing note

**Strength Guidelines:**
- 1.0: Very strong/direct relationship
- 0.7-0.9: Clear relationship
- 0.5-0.6: Moderate relationship
- 0.3-0.4: Weak relationship
- Below 0.3: Don't create relationship

**Format your response as JSON:**
\`\`\`json
{
  "relationships": [
    {
      "to_note_id": "note-id",
      "relationship_type": "related_to|contradicts|refines|context_for|follows_from",
      "strength": 0.85,
      "reasoning": "brief explanation"
    }
  ]
}
\`\`\`

**Guidelines:**
- Only create relationships with strength >= 0.3
- Contradictions should be rare and obvious
- Most relationships will be "related_to" or "refines"
- Focus on meaningful connections, not superficial similarities
- Limit to top 5 strongest relationships

**Example:**

New Note: "uses vim keybindings"
Existing Notes:
1. [abc123] prefers VSCode | preference:editor
2. [def456] learning Python | skill:programming
3. [ghi789] prefers keyboard shortcuts | preference:ui

Response:
\`\`\`json
{
  "relationships": [
    {
      "to_note_id": "abc123",
      "relationship_type": "context_for",
      "strength": 0.9,
      "reasoning": "vim keybindings are used within VSCode editor"
    },
    {
      "to_note_id": "ghi789",
      "relationship_type": "related_to",
      "strength": 0.7,
      "reasoning": "both relate to keyboard-driven workflow preferences"
    }
  ]
}
\`\`\`

Now analyze relationships for the new note above:`}
                                            </pre>
                                        </div>
                                    )}
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
    );
};

export default SettingsPage;
