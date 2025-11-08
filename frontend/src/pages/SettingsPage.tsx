import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getSettings } from "../services/api";

const SettingsPage: React.FC = () => {
    const [settings, setSettings] = useState<any>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

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
                                Phase 1
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

                {/* Information Banner */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-8">
                    <h2 className="text-lg font-semibold text-blue-900 mb-2">
                        📋 Phase 1: Read-Only Configuration
                    </h2>
                    <p className="text-blue-800 mb-3">
                        Settings are configured via environment variables and cannot be changed from the UI.
                        To modify settings, update your <code className="bg-blue-100 px-2 py-1 rounded">.env</code> file and restart the service.
                    </p>
                    <div className="text-sm text-blue-700">
                        <p className="mb-2"><strong>To change settings:</strong></p>
                        <ol className="list-decimal list-inside space-y-1 ml-2">
                            <li>Edit <code className="bg-blue-100 px-1 rounded">.env</code> file in project root</li>
                            <li>Update <code className="bg-blue-100 px-1 rounded">EMBEDDINGS_*</code> environment variables</li>
                            <li>Restart: <code className="bg-blue-100 px-1 rounded">docker-compose restart</code></li>
                        </ol>
                    </div>
                </div>

                {/* Current Configuration */}
                <div className="bg-white rounded-lg shadow-md">
                    <div className="px-6 py-4 border-b border-gray-200">
                        <h2 className="text-xl font-bold text-gray-900">
                            Current Embeddings Configuration
                        </h2>
                    </div>

                    <div className="p-6">
                        {settings ? (
                            <div className="space-y-6">
                                {/* Provider */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Provider
                                    </label>
                                    <div className="flex items-center">
                                        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getProviderBadgeColor(settings.embeddings_provider)}`}>
                                            {settings.embeddings_provider}
                                        </span>
                                    </div>
                                    <p className="mt-1 text-xs text-gray-500">
                                        Environment variable: <code className="bg-gray-100 px-1 rounded">EMBEDDINGS_PROVIDER</code>
                                    </p>
                                </div>

                                {/* Endpoint URL */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Endpoint URL
                                    </label>
                                    <div className="w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-900 font-mono text-sm">
                                        {settings.embeddings_endpoint_url}
                                    </div>
                                    <p className="mt-1 text-xs text-gray-500">
                                        Environment variable: <code className="bg-gray-100 px-1 rounded">EMBEDDINGS_ENDPOINT_URL</code>
                                    </p>
                                </div>

                                {/* Model */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Model
                                    </label>
                                    <div className="w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-900">
                                        {settings.embeddings_model}
                                    </div>
                                    <p className="mt-1 text-xs text-gray-500">
                                        Environment variable: <code className="bg-gray-100 px-1 rounded">EMBEDDINGS_MODEL</code>
                                    </p>
                                </div>

                                {/* API Key */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        API Key
                                    </label>
                                    <div className="w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-900 font-mono text-sm">
                                        {settings.embeddings_api_key || <span className="text-gray-400 italic">Not configured</span>}
                                    </div>
                                    <p className="mt-1 text-xs text-gray-500">
                                        Environment variable: <code className="bg-gray-100 px-1 rounded">EMBEDDINGS_API_KEY</code>
                                    </p>
                                </div>

                                {/* Timeout */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Timeout (seconds)
                                    </label>
                                    <div className="w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-900">
                                        {settings.embeddings_timeout}
                                    </div>
                                    <p className="mt-1 text-xs text-gray-500">
                                        Environment variable: <code className="bg-gray-100 px-1 rounded">EMBEDDINGS_TIMEOUT</code>
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
