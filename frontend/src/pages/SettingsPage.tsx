import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import TagInput from "../components/TagInput";
import { getSettings, updateSettings } from "../services/api";
import { LLMSettings } from "../types";

const SettingsPage: React.FC = () => {
    const [settings, setSettings] = useState<LLMSettings | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [saving, setSaving] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<boolean>(false);
    const [memoryCategories, setMemoryCategories] = useState<string[]>([]);
    const [showPreview, setShowPreview] = useState(false);

    // Track template variables
    const [templateVariables] = useState([
        "{{ memory_categories_json }}",
        "{{ memory_categories_list }}",
        "{{ memory_categories }}",
    ]);

    // Ref to track if template variables are present
    const promptTextareaRef = useRef<HTMLTextAreaElement>(null);

    // Function to check if template variables are present in prompt
    const hasTemplateVariables = (prompt: string) => {
        return templateVariables.some((variable) => prompt.includes(variable));
    };

    // Function to suggest adding template variables if missing
    const suggestTemplateVariables = (prompt: string) => {
        const missing = templateVariables.filter(
            (variable) => !prompt.includes(variable)
        );
        return missing;
    };

    // Handle prompt change with template variable checking
    const handlePromptChange = (value: string) => {
        if (!settings) return;
        setSettings({ ...settings, memory_extraction_prompt: value });
    };

    // Insert template variable at cursor position
    const insertTemplateVariable = (variable: string) => {
        if (!promptTextareaRef.current || !settings) return;

        const textarea = promptTextareaRef.current;
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const currentPrompt = settings.memory_extraction_prompt;

        const newPrompt =
            currentPrompt.substring(0, start) +
            variable +
            currentPrompt.substring(end);

        setSettings({ ...settings, memory_extraction_prompt: newPrompt });

        // Restore cursor position after the inserted variable
        setTimeout(() => {
            textarea.focus();
            textarea.setSelectionRange(
                start + variable.length,
                start + variable.length
            );
        }, 0);
    };

    // Function to preview rendered template (client-side approximation)
    const getPreviewPrompt = () => {
        if (!settings) return "";

        let preview = settings.memory_extraction_prompt;
        const categoriesJson = memoryCategories
            .map((cat) => `"${cat}"`)
            .join(", ");
        const categoriesList = memoryCategories.join(", ");

        preview = preview.replace(
            /\{\{\s*memory_categories_json\s*\}\}/g,
            categoriesJson
        );
        preview = preview.replace(
            /\{\{\s*memory_categories_list\s*\}\}/g,
            categoriesList
        );
        preview = preview.replace(
            /\{\{\s*memory_categories\s*\}\}/g,
            `[${categoriesJson}]`
        );

        return preview;
    };

    useEffect(() => {
        const fetchSettings = async () => {
            try {
                const fetchedSettings = await getSettings();
                setSettings(fetchedSettings);
                if (fetchedSettings.memory_categories_list) {
                    setMemoryCategories(fetchedSettings.memory_categories_list);
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

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!settings) return;

        // Warn if template variables are missing
        const missing = suggestTemplateVariables(
            settings.memory_extraction_prompt
        );
        if (missing.length === templateVariables.length) {
            const proceed = window.confirm(
                `Warning: Your prompt is missing template variables: ${missing.join(
                    ", "
                )}\n\n` +
                    "Without specifying at least one of these variables, memory categories won't be dynamically inserted. As a result, no memories will be extracted. " +
                    "Continue saving anyway?"
            );
            if (!proceed) return;
        }

        setSaving(true);
        setError(null);
        setSuccess(false);

        try {
            const payload = {
                ...settings,
                memory_categories_list: memoryCategories,
            };
            const updatedSettings = await updateSettings(payload);
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
        );
    }

    const missingVariables = settings
        ? suggestTemplateVariables(settings.memory_extraction_prompt)
        : [];
    const hasVariables = settings
        ? hasTemplateVariables(settings.memory_extraction_prompt)
        : false;

    return (
        <div className="min-h-screen bg-gray-50">
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="bg-white shadow rounded-lg">
                    <div className="px-6 py-4 border-b border-gray-200">
                        <div className="flex items-center justify-between">
                            <div>
                                <h1 className="text-2xl font-bold text-gray-900">
                                    LLM Settings
                                </h1>
                                <p className="mt-1 text-sm text-gray-600">
                                    Configure your LLM endpoints and models for
                                    memory extraction and retrieval.
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

                    <form
                        onSubmit={handleSubmit}
                        className="px-6 py-4 space-y-6"
                    >
                        {/* Memory Extraction Settings */}
                        <div className="border-b border-gray-200 pb-6">
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
                                                e.target.value as any
                                            )
                                        }
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    >
                                        <option value="openai">OpenAI</option>
                                        <option value="openai_compatible">
                                            OpenAI Compatible
                                        </option>
                                        <option value="ollama">Ollama</option>
                                    </select>
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Model
                                    </label>
                                    <input
                                        type="text"
                                        value={settings.extraction_model}
                                        onChange={(e) =>
                                            handleInputChange(
                                                "extraction_model",
                                                e.target.value
                                            )
                                        }
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        placeholder="e.g., gpt-4, llama2"
                                    />
                                </div>

                                <div className="md:col-span-2">
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Endpoint URL
                                    </label>
                                    <input
                                        type="url"
                                        value={settings.extraction_endpoint_url}
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
                                        type="text"
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
                                        placeholder="Your API key for the LLM endpoint"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Timeout (seconds)
                                    </label>
                                    <input
                                        type="number"
                                        value={settings.extraction_timeout}
                                        onChange={(e) =>
                                            handleInputChange(
                                                "extraction_timeout",
                                                e.target.value
                                            )
                                        }
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        placeholder="Timeout for LLM requests"
                                    />
                                </div>
                                <div className="md:col-span-2">
                                    <div className="flex items-center justify-between mb-2">
                                        <label className="block text-sm font-medium text-gray-700">
                                            Memory Extraction Prompt
                                        </label>
                                        <div className="flex items-center space-x-2">
                                            <button
                                                type="button"
                                                onClick={() =>
                                                    setShowPreview(!showPreview)
                                                }
                                                className="text-sm text-blue-600 hover:text-blue-800"
                                            >
                                                {showPreview
                                                    ? "Hide Preview"
                                                    : "Show Preview"}
                                            </button>
                                            {!hasVariables && (
                                                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                                                    Missing template variables
                                                </span>
                                            )}
                                            {hasVariables && (
                                                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                                    ✓ Template variables
                                                    detected
                                                </span>
                                            )}
                                        </div>
                                    </div>

                                    {/* Template variable insertion buttons */}
                                    <div className="mb-2 flex flex-wrap gap-2">
                                        <span className="text-xs text-gray-600">
                                            Insert template variables:
                                        </span>
                                        {templateVariables.map((variable) => (
                                            <button
                                                key={variable}
                                                type="button"
                                                onClick={() =>
                                                    insertTemplateVariable(
                                                        variable
                                                    )
                                                }
                                                className="inline-flex items-center px-2 py-1 rounded text-xs font-mono bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
                                                title={`Insert ${variable}`}
                                            >
                                                {variable}
                                            </button>
                                        ))}
                                    </div>

                                    <textarea
                                        ref={promptTextareaRef}
                                        value={
                                            settings.memory_extraction_prompt
                                        }
                                        onChange={(e) =>
                                            handlePromptChange(e.target.value)
                                        }
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                                        rows={12}
                                        placeholder="Prompt for the LLM to extract memories from conversations"
                                    />

                                    {/* Preview section */}
                                    {showPreview && (
                                        <div className="mb-4 p-4 bg-gray-50 border rounded-md">
                                            <div className="text-sm font-medium text-gray-700 mb-2">
                                                Template Preview:
                                            </div>
                                            <pre className="text-xs text-gray-600 whitespace-pre-wrap overflow-auto max-h-64">
                                                {getPreviewPrompt()}
                                            </pre>
                                        </div>
                                    )}

                                    {/* Template variable help */}
                                    <div className="mt-2 text-xs text-gray-500 space-y-1">
                                        <div className="font-medium">
                                            Available template variables:
                                        </div>
                                        <div>
                                            •{" "}
                                            <code className="bg-gray-100 px-1 rounded">
                                                {"{{ memory_categories_json }}"}
                                            </code>{" "}
                                            - JSON array format: ["identity",
                                            "behavior"]
                                        </div>
                                        <div>
                                            •{" "}
                                            <code className="bg-gray-100 px-1 rounded">
                                                {"{{ memory_categories_list }}"}
                                            </code>{" "}
                                            - Comma-separated: identity,
                                            behavior
                                        </div>
                                        <div>
                                            •{" "}
                                            <code className="bg-gray-100 px-1 rounded">
                                                {"{{ memory_categories }}"}
                                            </code>{" "}
                                            - Python list format
                                        </div>
                                        {missingVariables.length > 0 && (
                                            <div className="text-yellow-600 font-medium">
                                                Missing variables:{" "}
                                                {missingVariables.join(", ")}
                                            </div>
                                        )}
                                    </div>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Memory Categories
                                    </label>
                                    <TagInput
                                        value={memoryCategories}
                                        onChange={setMemoryCategories}
                                        placeholder="Type a category and press space..."
                                        className="w-full"
                                    />
                                    <p className="text-xs text-gray-500 mt-1">
                                        Categories used for memory
                                        classification. Type a word and press
                                        space to add.
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Embeddings Settings */}
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
                                                e.target.value as any
                                            )
                                        }
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    >
                                        <option value="openai_compatible">
                                            OpenAI Compatible
                                        </option>
                                        <option value="ollama">Ollama</option>
                                    </select>
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Model
                                    </label>
                                    <input
                                        type="text"
                                        value={settings.embeddings_model}
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
                                        value={settings.embeddings_endpoint_url}
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
                                        type="text"
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
                                        placeholder="Your API key for the embeddings endpoint"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Timeout (seconds)
                                    </label>
                                    <input
                                        type="number"
                                        value={settings.embeddings_timeout}
                                        onChange={(e) =>
                                            handleInputChange(
                                                "embeddings_timeout",
                                                e.target.value
                                            )
                                        }
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        placeholder="Timeout for embeddings requests"
                                    />
                                </div>
                            </div>
                        </div>

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
                        <div className="flex justify-end">
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
