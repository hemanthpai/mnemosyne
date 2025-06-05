import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { deleteMemory, getMemory, updateMemory } from "../services/api";
import { Memory } from "../types";

const MemoryDetailPage: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const [memory, setMemory] = useState<Memory | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [isEditing, setIsEditing] = useState<boolean>(false);
    const [editedContent, setEditedContent] = useState<string>("");
    const [editedMetadata, setEditedMetadata] = useState<string>("");

    useEffect(() => {
        const fetchMemory = async () => {
            if (!id) return;

            try {
                const fetchedMemory = await getMemory(id);
                setMemory(fetchedMemory);
                setEditedContent(fetchedMemory.content);
                setEditedMetadata(
                    JSON.stringify(fetchedMemory.metadata, null, 2)
                );
            } catch (err) {
                setError("Failed to fetch memory");
                console.error("Error fetching memory:", err);
            } finally {
                setLoading(false);
            }
        };

        fetchMemory();
    }, [id]);

    const handleSave = async () => {
        if (!memory || !id) return;

        try {
            let parsedMetadata = {};
            if (editedMetadata.trim()) {
                parsedMetadata = JSON.parse(editedMetadata);
            }

            const updatedMemory = await updateMemory(
                id,
                {
                    content: editedContent,
                    metadata: parsedMetadata,
                },
                true
            );

            setMemory(updatedMemory);
            setIsEditing(false);
        } catch (err) {
            setError("Failed to update memory");
            console.error("Error updating memory:", err);
        }
    };

    const handleDelete = async () => {
        if (!id || !confirm("Are you sure you want to delete this memory?"))
            return;

        try {
            await deleteMemory(id);
            navigate("/memories");
        } catch (err) {
            setError("Failed to delete memory");
            console.error("Error deleting memory:", err);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                    <p className="mt-2 text-gray-600">Loading memory...</p>
                </div>
            </div>
        );
    }

    if (error || !memory) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                    <p className="text-red-600">
                        {error || "Memory not found"}
                    </p>
                    <button
                        onClick={() => navigate("/memories")}
                        className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                    >
                        Back to Memories
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50">
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="bg-white shadow rounded-lg">
                    <div className="px-6 py-4 border-b border-gray-200">
                        <div className="flex items-center justify-between">
                            <h1 className="text-2xl font-bold text-gray-900">
                                Memory Details
                            </h1>
                            <div className="flex space-x-2">
                                {isEditing ? (
                                    <>
                                        <button
                                            onClick={handleSave}
                                            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
                                        >
                                            Save
                                        </button>
                                        <button
                                            onClick={() => setIsEditing(false)}
                                            className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
                                        >
                                            Cancel
                                        </button>
                                    </>
                                ) : (
                                    <>
                                        <button
                                            onClick={() => setIsEditing(true)}
                                            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                                        >
                                            Edit
                                        </button>
                                        <button
                                            onClick={handleDelete}
                                            className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
                                        >
                                            Delete
                                        </button>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="px-6 py-4">
                        <div className="grid grid-cols-2 gap-4 mb-6">
                            <div>
                                <label className="block text-sm font-medium text-gray-700">
                                    ID
                                </label>
                                <p className="mt-1 text-sm text-gray-900">
                                    {memory.id}
                                </p>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700">
                                    User ID
                                </label>
                                <p className="mt-1 text-sm text-gray-900">
                                    {memory.user_id}
                                </p>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700">
                                    Created
                                </label>
                                <p className="mt-1 text-sm text-gray-900">
                                    {new Date(
                                        memory.created_at
                                    ).toLocaleString()}
                                </p>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700">
                                    Updated
                                </label>
                                <p className="mt-1 text-sm text-gray-900">
                                    {new Date(
                                        memory.updated_at
                                    ).toLocaleString()}
                                </p>
                            </div>
                        </div>

                        <div className="mb-6">
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                Content
                            </label>
                            {isEditing ? (
                                <textarea
                                    value={editedContent}
                                    onChange={(e) =>
                                        setEditedContent(e.target.value)
                                    }
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    rows={6}
                                />
                            ) : (
                                <div className="bg-gray-50 p-4 rounded-md">
                                    <p className="text-gray-900 whitespace-pre-wrap">
                                        {memory.content}
                                    </p>
                                </div>
                            )}
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                Metadata
                            </label>
                            {isEditing ? (
                                <textarea
                                    value={editedMetadata}
                                    onChange={(e) =>
                                        setEditedMetadata(e.target.value)
                                    }
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                                    rows={8}
                                    placeholder="Enter valid JSON"
                                />
                            ) : (
                                <div className="bg-gray-50 p-4 rounded-md">
                                    <pre className="text-sm text-gray-900 whitespace-pre-wrap">
                                        {JSON.stringify(
                                            memory.metadata,
                                            null,
                                            2
                                        )}
                                    </pre>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="mt-6">
                    <button
                        onClick={() => navigate("/memories")}
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
                        Back to Memories
                    </button>
                </div>
            </div>
        </div>
    );
};

export default MemoryDetailPage;
