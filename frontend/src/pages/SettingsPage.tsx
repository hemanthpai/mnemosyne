import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getSettings, updateSettings } from "../services/api";

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

    const hasChanges = JSON.stringify(settings) !== JSON.stringify(editedSettings);

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
                    <p className="mt-2 text-gray-600">Loading settings...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="bg-red-50 border border-red-200 rounded-lg p-6">
                    <p className="text-red-800">{error}</p>
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
                            <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
                            <span className="ml-3 text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                                Configuration
                            </span>
                        </div>
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
            </header>

            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Save Status Messages */}
                {saveSuccess && (
                    <div className="mb-6 bg-green-50 border border-green-200 rounded-lg p-4">
                        <p className="text-green-800">{saveSuccess}</p>
                    </div>
                )}

                {saveError && (
                    <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
                        <p className="text-red-800">{saveError}</p>
                    </div>
                )}

                {/* Information Banner */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-8">
                    <h2 className="text-lg font-semibold text-blue-900 mb-2">
                        ⚙️ Editable Configuration
                    </h2>
                    <p className="text-blue-800">
                        Settings are stored in the database and can be edited directly from this page.
                        Changes take effect immediately without requiring a restart.
                    </p>
                </div>

                {/* Tabs */}
                <div className="bg-white rounded-lg shadow-md">
                    {/* Tab Navigation */}
                    <div className="border-b border-gray-200">
                        <nav className="flex -mb-px">
                            <button
                                onClick={() => setActiveTab('embeddings')}
                                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                                    activeTab === 'embeddings'
                                        ? 'border-blue-500 text-blue-600'
                                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                }`}
                            >
                                Embeddings
                            </button>
                            <button
                                onClick={() => setActiveTab('generation')}
                                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                                    activeTab === 'generation'
                                        ? 'border-blue-500 text-blue-600'
                                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                }`}
                            >
                                Generation
                            </button>
                            <button
                                onClick={() => setActiveTab('prompts')}
                                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                                    activeTab === 'prompts'
                                        ? 'border-blue-500 text-blue-600'
                                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                }`}
                            >
                                Prompts
                            </button>
                        </nav>
                    </div>

                    {/* Tab Content */}
                    <div className="p-6">
                        {/* Embeddings Tab */}
                        {activeTab === 'embeddings' && (
                            <div className="space-y-6">
                                <div>
                                    <h3 className="text-lg font-semibold text-gray-900 mb-4">
                                        Embeddings Configuration
                                    </h3>
                                    <p className="text-sm text-gray-600 mb-6">
                                        Configuration for generating embeddings used in semantic search and vector storage.
                                    </p>
                                </div>

                                {/* Provider */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Provider
                                    </label>
                                    <select
                                        value={editedSettings.embeddings_provider}
                                        onChange={(e) => handleFieldChange('embeddings_provider', e.target.value)}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    >
                                        <option value="ollama">Ollama</option>
                                        <option value="openai">OpenAI</option>
                                        <option value="openai_compatible">OpenAI Compatible</option>
                                    </select>
                                </div>

                                {/* Endpoint URL */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Endpoint URL
                                    </label>
                                    <input
                                        type="text"
                                        value={editedSettings.embeddings_endpoint_url}
                                        onChange={(e) => handleFieldChange('embeddings_endpoint_url', e.target.value)}
                                        placeholder="http://localhost:11434"
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                {/* Model */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Model
                                    </label>
                                    <input
                                        type="text"
                                        value={editedSettings.embeddings_model}
                                        onChange={(e) => handleFieldChange('embeddings_model', e.target.value)}
                                        placeholder="mxbai-embed-large"
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                {/* API Key */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        API Key (Optional)
                                    </label>
                                    <input
                                        type="password"
                                        value={editedSettings.embeddings_api_key}
                                        onChange={(e) => handleFieldChange('embeddings_api_key', e.target.value)}
                                        placeholder="••••••••"
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    <p className="mt-1 text-xs text-gray-500">
                                        Leave empty for providers that don't require authentication
                                    </p>
                                </div>

                                {/* Timeout */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Timeout (seconds)
                                    </label>
                                    <input
                                        type="number"
                                        min="1"
                                        max="600"
                                        value={editedSettings.embeddings_timeout}
                                        onChange={(e) => handleFieldChange('embeddings_timeout', parseInt(e.target.value))}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                            </div>
                        )}

                        {/* Generation Tab */}
                        {activeTab === 'generation' && (
                            <div className="space-y-6">
                                <div>
                                    <h3 className="text-lg font-semibold text-gray-900 mb-4">
                                        Generation Configuration
                                    </h3>
                                    <p className="text-sm text-gray-600 mb-6">
                                        Separate configuration for text generation (atomic note extraction, relationship building).
                                        Leave fields blank to use embeddings configuration.
                                    </p>
                                </div>

                                {/* Provider */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Provider
                                    </label>
                                    <select
                                        value={editedSettings.generation_provider || ''}
                                        onChange={(e) => handleFieldChange('generation_provider', e.target.value)}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    >
                                        <option value="">(use embeddings provider)</option>
                                        <option value="ollama">Ollama</option>
                                        <option value="openai">OpenAI</option>
                                        <option value="openai_compatible">OpenAI Compatible</option>
                                    </select>
                                </div>

                                {/* Endpoint URL */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Endpoint URL
                                    </label>
                                    <input
                                        type="text"
                                        value={editedSettings.generation_endpoint_url || ''}
                                        onChange={(e) => handleFieldChange('generation_endpoint_url', e.target.value)}
                                        placeholder="(use embeddings endpoint)"
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                {/* Model */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Model
                                    </label>
                                    <input
                                        type="text"
                                        value={editedSettings.generation_model || ''}
                                        onChange={(e) => handleFieldChange('generation_model', e.target.value)}
                                        placeholder="(use embeddings model)"
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                {/* API Key */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        API Key
                                    </label>
                                    <input
                                        type="password"
                                        value={editedSettings.generation_api_key || ''}
                                        onChange={(e) => handleFieldChange('generation_api_key', e.target.value)}
                                        placeholder="(use embeddings API key)"
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                {/* Temperature */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Temperature (0.0 - 1.0)
                                    </label>
                                    <input
                                        type="number"
                                        min="0"
                                        max="1"
                                        step="0.1"
                                        value={editedSettings.generation_temperature}
                                        onChange={(e) => handleFieldChange('generation_temperature', parseFloat(e.target.value))}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    <p className="mt-1 text-xs text-gray-500">
                                        Higher values = more creative, lower values = more focused
                                    </p>
                                </div>

                                {/* Max Tokens */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Max Tokens
                                    </label>
                                    <input
                                        type="number"
                                        min="1"
                                        max="100000"
                                        value={editedSettings.generation_max_tokens}
                                        onChange={(e) => handleFieldChange('generation_max_tokens', parseInt(e.target.value))}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                {/* Timeout */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Timeout (seconds)
                                    </label>
                                    <input
                                        type="number"
                                        min="1"
                                        max="600"
                                        value={editedSettings.generation_timeout}
                                        onChange={(e) => handleFieldChange('generation_timeout', parseInt(e.target.value))}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                            </div>
                        )}

                        {/* Prompts Tab */}
                        {activeTab === 'prompts' && (
                            <div className="space-y-6">
                                <div>
                                    <h3 className="text-lg font-semibold text-gray-900 mb-4">
                                        Prompt Customization
                                    </h3>
                                    <p className="text-sm text-gray-600 mb-6">
                                        Customize the prompts used for atomic note extraction and relationship building.
                                        Leave empty to use default prompts. Prompts should include template variables.
                                    </p>
                                </div>

                                {/* Extraction Prompt */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Extraction Prompt
                                    </label>
                                    <textarea
                                        value={editedSettings.extraction_prompt || ''}
                                        onChange={(e) => handleFieldChange('extraction_prompt', e.target.value)}
                                        placeholder="Leave empty to use default extraction prompt"
                                        rows={12}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                                    />
                                    <p className="mt-1 text-xs text-gray-500">
                                        Required template variables: {'{user_message}'}, {'{assistant_message}'}
                                    </p>
                                </div>

                                {/* Relationship Prompt */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Relationship Prompt
                                    </label>
                                    <textarea
                                        value={editedSettings.relationship_prompt || ''}
                                        onChange={(e) => handleFieldChange('relationship_prompt', e.target.value)}
                                        placeholder="Leave empty to use default relationship prompt"
                                        rows={12}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                                    />
                                    <p className="mt-1 text-xs text-gray-500">
                                        Required template variables: {'{new_note_content}'}, {'{new_note_type}'}, {'{new_note_context}'}, {'{existing_notes}'}
                                    </p>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Action Buttons */}
                    <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex justify-end space-x-3">
                        <button
                            onClick={handleReset}
                            disabled={!hasChanges || saving}
                            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            Reset
                        </button>
                        <button
                            onClick={handleSave}
                            disabled={!hasChanges || saving}
                            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                            {saving ? 'Saving...' : 'Save Changes'}
                        </button>
                    </div>
                </div>
            </main>
        </div>
    );
};

export default SettingsPage;
