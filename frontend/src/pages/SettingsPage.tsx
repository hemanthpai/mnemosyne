import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getSettings, updateSettings } from "../services/api";

const SettingsPage: React.FC = () => {
    const [settings, setSettings] = useState<any>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [editMode, setEditMode] = useState<boolean>(false);
    const [editedSettings, setEditedSettings] = useState<any>(null);
    const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [saving, setSaving] = useState<boolean>(false);

    useEffect(() => {
        const fetchSettings = async () => {
            try {
                const response = await getSettings();
                setSettings(response.settings);
            } catch (err) {
                setError("Failed to fetch settings");
                console.error("Error fetching settings:", err);
            } finally {
                setLoading(false);
            }
        };

        fetchSettings();
    }, []);

    const handleEdit = () => {
        setEditedSettings({ ...settings });
        setEditMode(true);
        setSaveSuccess(null);
        setSaveError(null);
    };

    const handleCancel = () => {
        setEditedSettings(null);
        setEditMode(false);
        setSaveError(null);
    };

    const handleSave = async () => {
        setSaving(true);
        setSaveError(null);
        setSaveSuccess(null);

        try {
            const response = await updateSettings(editedSettings);
            setSettings(response.settings);
            setEditMode(false);
            setEditedSettings(null);
            setSaveSuccess(response.message || "Settings updated successfully!");

            // Clear success message after 5 seconds
            setTimeout(() => setSaveSuccess(null), 5000);
        } catch (err: any) {
            const errorMessage = err.response?.data?.error || "Failed to update settings";
            setSaveError(errorMessage);
            console.error("Error updating settings:", err);
        } finally {
            setSaving(false);
        }
    };

    const handleFieldChange = (field: string, value: any) => {
        setEditedSettings({
            ...editedSettings,
            [field]: value
        });
    };

    const getProviderBadgeColor = (provider: string) => {
        switch (provider?.toLowerCase()) {
            case 'ollama':
                return 'bg-green-100 text-green-800';
            case 'openai':
                return 'bg-blue-100 text-blue-800';
            case 'openai_compatible':
                return 'bg-purple-100 text-purple-800';
            default:
                return 'bg-gray-100 text-gray-800';
        }
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
                {error && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                        <p className="text-red-800">{error}</p>
                    </div>
                )}

                {/* Success/Error Messages */}
                {saveSuccess && (
                    <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
                        <p className="text-green-800 flex items-center">
                            <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                            {saveSuccess}
                        </p>
                    </div>
                )}
                {saveError && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                        <p className="text-red-800 flex items-center">
                            <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                            </svg>
                            {saveError}
                        </p>
                    </div>
                )}

                {/* Information Banner */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-8">
                    <h2 className="text-lg font-semibold text-blue-900 mb-2">
                        ⚙️ Phase 3: Editable Configuration
                    </h2>
                    <p className="text-blue-800 mb-3">
                        Settings are stored in the database and can be edited directly from this page.
                        Changes take effect immediately without requiring a restart.
                    </p>
                    <div className="text-sm text-blue-700">
                        <p className="mb-2"><strong>To change settings:</strong></p>
                        <ol className="list-decimal list-inside space-y-1 ml-2">
                            <li>Click the "Edit Settings" button below</li>
                            <li>Modify any fields you wish to update</li>
                            <li>Click "Save Changes" to apply (or "Cancel" to discard)</li>
                        </ol>
                    </div>
                </div>

                {/* Current Configuration */}
                <div className="bg-white rounded-lg shadow-md">
                    <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
                        <h2 className="text-xl font-bold text-gray-900">
                            Current Embeddings Configuration
                        </h2>
                        <div className="flex gap-2">
                            {!editMode ? (
                                <button
                                    onClick={handleEdit}
                                    className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors duration-200"
                                >
                                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                    </svg>
                                    Edit Settings
                                </button>
                            ) : (
                                <>
                                    <button
                                        onClick={handleCancel}
                                        disabled={saving}
                                        className="inline-flex items-center px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                        </svg>
                                        Cancel
                                    </button>
                                    <button
                                        onClick={handleSave}
                                        disabled={saving}
                                        className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {saving ? (
                                            <>
                                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                                                Saving...
                                            </>
                                        ) : (
                                            <>
                                                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                                </svg>
                                                Save Changes
                                            </>
                                        )}
                                    </button>
                                </>
                            )}
                        </div>
                    </div>

                    <div className="p-6">
                        {settings ? (
                            <div className="space-y-6">
                                {/* Provider */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Provider
                                    </label>
                                    {editMode ? (
                                        <select
                                            value={editedSettings.embeddings_provider}
                                            onChange={(e) => handleFieldChange('embeddings_provider', e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        >
                                            <option value="ollama">ollama</option>
                                            <option value="openai">openai</option>
                                            <option value="openai_compatible">openai_compatible</option>
                                        </select>
                                    ) : (
                                        <div className="flex items-center">
                                            <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getProviderBadgeColor(settings.embeddings_provider)}`}>
                                                {settings.embeddings_provider}
                                            </span>
                                        </div>
                                    )}
                                    <p className="mt-1 text-xs text-gray-500">
                                        {editMode ? 'Select the embeddings provider to use' : 'Stored in database (overrides environment variable)'}
                                    </p>
                                </div>

                                {/* Endpoint URL */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Endpoint URL
                                    </label>
                                    {editMode ? (
                                        <input
                                            type="text"
                                            value={editedSettings.embeddings_endpoint_url}
                                            onChange={(e) => handleFieldChange('embeddings_endpoint_url', e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            placeholder="http://host.docker.internal:11434"
                                        />
                                    ) : (
                                        <div className="w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-900 font-mono text-sm">
                                            {settings.embeddings_endpoint_url}
                                        </div>
                                    )}
                                    <p className="mt-1 text-xs text-gray-500">
                                        {editMode ? 'API endpoint URL for the embeddings service' : 'Stored in database (overrides environment variable)'}
                                    </p>
                                </div>

                                {/* Model */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Embeddings Model
                                    </label>
                                    {editMode ? (
                                        <input
                                            type="text"
                                            value={editedSettings.embeddings_model}
                                            onChange={(e) => handleFieldChange('embeddings_model', e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            placeholder="mxbai-embed-large"
                                        />
                                    ) : (
                                        <div className="w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-900">
                                            {settings.embeddings_model}
                                        </div>
                                    )}
                                    <p className="mt-1 text-xs text-gray-500">
                                        {editMode ? 'Model name for generating embeddings' : 'Stored in database (overrides environment variable)'}
                                    </p>
                                </div>

                                {/* API Key */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        API Key
                                    </label>
                                    {editMode ? (
                                        <input
                                            type="password"
                                            value={editedSettings.embeddings_api_key}
                                            onChange={(e) => handleFieldChange('embeddings_api_key', e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            placeholder="Optional - leave blank if not needed"
                                        />
                                    ) : (
                                        <div className="w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-900 font-mono text-sm">
                                            {settings.embeddings_api_key || <span className="text-gray-400 italic">Not configured</span>}
                                        </div>
                                    )}
                                    <p className="mt-1 text-xs text-gray-500">
                                        {editMode ? 'Optional - only required for some providers (OpenAI, etc.)' : 'Stored in database (masked for security)'}
                                    </p>
                                </div>

                                {/* Timeout */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Timeout (seconds)
                                    </label>
                                    {editMode ? (
                                        <input
                                            type="number"
                                            min="1"
                                            max="600"
                                            value={editedSettings.embeddings_timeout}
                                            onChange={(e) => handleFieldChange('embeddings_timeout', parseInt(e.target.value))}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        />
                                    ) : (
                                        <div className="w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-900">
                                            {settings.embeddings_timeout}
                                        </div>
                                    )}
                                    <p className="mt-1 text-xs text-gray-500">
                                        {editMode ? 'Request timeout in seconds (1-600)' : 'Stored in database (overrides environment variable)'}
                                    </p>
                                </div>

                            </div>
                        ) : (
                            <p className="text-gray-500 text-center py-8">No settings available</p>
                        )}
                    </div>
                </div>

                {/* Generation Configuration (Phase 3) */}
                <div className="mt-8 bg-white rounded-lg shadow-md">
                    <div className="px-6 py-4 border-b border-gray-200">
                        <h2 className="text-xl font-bold text-gray-900">
                            Generation Configuration (Phase 3)
                        </h2>
                        <p className="mt-1 text-sm text-gray-600">
                            Separate configuration for text generation (atomic note extraction, relationship building). Leave fields blank to use embeddings configuration.
                        </p>
                    </div>

                    <div className="p-6">
                        {settings ? (
                            <div className="space-y-6">
                                {/* Generation Provider */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Provider
                                    </label>
                                    {editMode ? (
                                        <select
                                            value={editedSettings.generation_provider || ''}
                                            onChange={(e) => handleFieldChange('generation_provider', e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        >
                                            <option value="">(use embeddings provider)</option>
                                            <option value="ollama">ollama</option>
                                            <option value="openai">openai</option>
                                            <option value="openai_compatible">openai_compatible</option>
                                        </select>
                                    ) : (
                                        <div className="flex items-center">
                                            <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getProviderBadgeColor(settings.generation_provider)}`}>
                                                {settings.generation_provider || `${settings.embeddings_provider} (default)`}
                                            </span>
                                        </div>
                                    )}
                                    <p className="mt-1 text-xs text-gray-500">
                                        {editMode ? 'Leave blank to use embeddings provider' : 'Provider for text generation'}
                                    </p>
                                </div>

                                {/* Generation Endpoint URL */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Endpoint URL
                                    </label>
                                    {editMode ? (
                                        <input
                                            type="text"
                                            value={editedSettings.generation_endpoint_url || ''}
                                            onChange={(e) => handleFieldChange('generation_endpoint_url', e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            placeholder="Leave blank to use embeddings endpoint"
                                        />
                                    ) : (
                                        <div className="w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-900 font-mono text-sm">
                                            {settings.generation_endpoint_url || <span className="text-gray-400 italic">{settings.embeddings_endpoint_url} (default)</span>}
                                        </div>
                                    )}
                                    <p className="mt-1 text-xs text-gray-500">
                                        {editMode ? 'Separate API endpoint for generation (e.g., use OpenAI for generation while Ollama handles embeddings)' : 'API endpoint for generation requests'}
                                    </p>
                                </div>

                                {/* Generation Model */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Model
                                    </label>
                                    {editMode ? (
                                        <input
                                            type="text"
                                            value={editedSettings.generation_model || ''}
                                            onChange={(e) => handleFieldChange('generation_model', e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            placeholder="Leave blank to use embeddings model"
                                        />
                                    ) : (
                                        <div className="w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-900">
                                            {settings.generation_model || <span className="text-gray-400 italic">{settings.embeddings_model} (default)</span>}
                                        </div>
                                    )}
                                    <p className="mt-1 text-xs text-gray-500">
                                        {editMode ? 'Model name for text generation (e.g., gpt-4, llama3, mistral)' : 'Model for atomic note extraction and relationship building'}
                                    </p>
                                </div>

                                {/* Generation API Key */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        API Key
                                    </label>
                                    {editMode ? (
                                        <input
                                            type="password"
                                            value={editedSettings.generation_api_key || ''}
                                            onChange={(e) => handleFieldChange('generation_api_key', e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            placeholder="Leave blank to use embeddings API key"
                                        />
                                    ) : (
                                        <div className="w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-900 font-mono text-sm">
                                            {settings.generation_api_key || <span className="text-gray-400 italic">Using embeddings API key</span>}
                                        </div>
                                    )}
                                    <p className="mt-1 text-xs text-gray-500">
                                        {editMode ? 'Separate API key for generation provider (if different from embeddings)' : 'Stored in database (masked for security)'}
                                    </p>
                                </div>

                                {/* Generation Temperature */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Temperature
                                    </label>
                                    {editMode ? (
                                        <input
                                            type="number"
                                            min="0"
                                            max="1"
                                            step="0.1"
                                            value={editedSettings.generation_temperature}
                                            onChange={(e) => handleFieldChange('generation_temperature', parseFloat(e.target.value))}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        />
                                    ) : (
                                        <div className="w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-900">
                                            {settings.generation_temperature}
                                        </div>
                                    )}
                                    <p className="mt-1 text-xs text-gray-500">
                                        {editMode ? 'Sampling temperature (0.0-1.0). Lower = more focused, higher = more creative. Default: 0.3' : 'Controls randomness in generation'}
                                    </p>
                                </div>

                                {/* Generation Max Tokens */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Max Tokens
                                    </label>
                                    {editMode ? (
                                        <input
                                            type="number"
                                            min="1"
                                            max="100000"
                                            value={editedSettings.generation_max_tokens}
                                            onChange={(e) => handleFieldChange('generation_max_tokens', parseInt(e.target.value))}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        />
                                    ) : (
                                        <div className="w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-900">
                                            {settings.generation_max_tokens}
                                        </div>
                                    )}
                                    <p className="mt-1 text-xs text-gray-500">
                                        {editMode ? 'Maximum tokens to generate per request (1-100000). Default: 1000' : 'Maximum length of generated text'}
                                    </p>
                                </div>

                                {/* Generation Timeout */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Timeout (seconds)
                                    </label>
                                    {editMode ? (
                                        <input
                                            type="number"
                                            min="1"
                                            max="600"
                                            value={editedSettings.generation_timeout}
                                            onChange={(e) => handleFieldChange('generation_timeout', parseInt(e.target.value))}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        />
                                    ) : (
                                        <div className="w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-900">
                                            {settings.generation_timeout}
                                        </div>
                                    )}
                                    <p className="mt-1 text-xs text-gray-500">
                                        {editMode ? 'Request timeout in seconds (1-600). Default: 60' : 'Timeout for generation requests'}
                                    </p>
                                </div>
                            </div>
                        ) : (
                            <p className="text-gray-500 text-center py-8">No settings available</p>
                        )}
                    </div>
                </div>

                {/* Configuration Examples */}
                <div className="mt-8 bg-white rounded-lg shadow-md">
                    <div className="px-6 py-4 border-b border-gray-200">
                        <h2 className="text-xl font-bold text-gray-900">
                            Configuration Examples
                        </h2>
                    </div>

                    <div className="p-6 space-y-6">
                        {/* Ollama Example */}
                        <div className="border border-gray-200 rounded-lg p-4">
                            <h3 className="text-lg font-semibold text-gray-900 mb-2 flex items-center">
                                <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-800 mr-2">
                                    Ollama
                                </span>
                                Local/Homeserver (Recommended)
                            </h3>
                            <pre className="bg-gray-900 text-gray-100 p-4 rounded-md overflow-x-auto text-sm mt-2">
{`EMBEDDINGS_PROVIDER=ollama
EMBEDDINGS_ENDPOINT_URL=http://host.docker.internal:11434
EMBEDDINGS_MODEL=mxbai-embed-large
EMBEDDINGS_TIMEOUT=30`}</pre>
                            <p className="mt-2 text-sm text-gray-600">
                                Requires Ollama running on host. Pull model: <code className="bg-gray-100 px-1 rounded">ollama pull mxbai-embed-large</code>
                            </p>
                        </div>

                        {/* OpenAI Example */}
                        <div className="border border-gray-200 rounded-lg p-4">
                            <h3 className="text-lg font-semibold text-gray-900 mb-2 flex items-center">
                                <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-800 mr-2">
                                    OpenAI
                                </span>
                                Cloud Service
                            </h3>
                            <pre className="bg-gray-900 text-gray-100 p-4 rounded-md overflow-x-auto text-sm mt-2">
{`EMBEDDINGS_PROVIDER=openai
EMBEDDINGS_ENDPOINT_URL=https://api.openai.com/v1
EMBEDDINGS_MODEL=text-embedding-3-small
EMBEDDINGS_API_KEY=sk-your-key-here
EMBEDDINGS_TIMEOUT=30`}</pre>
                            <p className="mt-2 text-sm text-gray-600">
                                Requires OpenAI API key. Cost: ~$0.00002 per 1K tokens
                            </p>
                        </div>

                        {/* OpenAI Compatible Example */}
                        <div className="border border-gray-200 rounded-lg p-4">
                            <h3 className="text-lg font-semibold text-gray-900 mb-2 flex items-center">
                                <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-purple-100 text-purple-800 mr-2">
                                    Compatible
                                </span>
                                LM Studio, vLLM, etc.
                            </h3>
                            <pre className="bg-gray-900 text-gray-100 p-4 rounded-md overflow-x-auto text-sm mt-2">
{`EMBEDDINGS_PROVIDER=openai_compatible
EMBEDDINGS_ENDPOINT_URL=http://your-server:8000/v1
EMBEDDINGS_MODEL=your-embedding-model
EMBEDDINGS_API_KEY=optional-if-needed
EMBEDDINGS_TIMEOUT=30`}</pre>
                            <p className="mt-2 text-sm text-gray-600">
                                For any service with OpenAI-compatible API (LM Studio, vLLM, Text Generation WebUI, etc.)
                            </p>
                        </div>
                    </div>
                </div>

                {/* Quick Links */}
                <div className="mt-8 bg-white rounded-lg shadow-md">
                    <div className="px-6 py-4 border-b border-gray-200">
                        <h2 className="text-xl font-bold text-gray-900">
                            Quick Links
                        </h2>
                    </div>

                    <div className="p-6">
                        <div className="grid md:grid-cols-2 gap-4">
                            <Link
                                to="/devtools"
                                className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                            >
                                <div className="flex-shrink-0 w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                                    <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                    </svg>
                                </div>
                                <div className="ml-4">
                                    <h3 className="text-sm font-semibold text-gray-900">Dev Tools</h3>
                                    <p className="text-sm text-gray-600">Test conversation storage and search</p>
                                </div>
                            </Link>

                            <a
                                href="https://github.com/anthropics/mnemosyne"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                            >
                                <div className="flex-shrink-0 w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                                    <svg className="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                </div>
                                <div className="ml-4">
                                    <h3 className="text-sm font-semibold text-gray-900">Documentation</h3>
                                    <p className="text-sm text-gray-600">Setup guides and architecture docs</p>
                                </div>
                            </a>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
};

export default SettingsPage;
