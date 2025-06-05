import React from "react";
import { Link } from "react-router-dom";
import { Memory } from "../types";

interface MemoryListProps {
    memories: Memory[];
}

const MemoryList: React.FC<MemoryListProps> = ({ memories }) => {
    if (memories.length === 0) {
        return (
            <div className="text-center py-12">
                <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <h3 className="mt-2 text-sm font-medium text-gray-900">No memories found</h3>
                <p className="mt-1 text-sm text-gray-500">Enter a User ID to view memories for that user.</p>
            </div>
        );
    }

    return (
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
            <ul className="divide-y divide-gray-200">
                {memories.map((memory) => (
                    <li key={memory.id}>
                        <Link to={`/memory/${memory.id}`} className="block hover:bg-gray-50">
                            <div className="px-4 py-4 sm:px-6">
                                <div className="flex items-center justify-between">
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-gray-900 truncate">
                                            {memory.content.substring(0, 100)}
                                            {memory.content.length > 100 && "..."}
                                        </p>
                                        <p className="text-sm text-gray-500">
                                            User: {memory.user_id}
                                        </p>
                                    </div>
                                    <div className="flex-shrink-0 text-sm text-gray-500">
                                        {new Date(memory.created_at).toLocaleDateString()}
                                    </div>
                                </div>
                                {Object.keys(memory.metadata).length > 0 && (
                                    <div className="mt-2">
                                        <div className="flex flex-wrap gap-1">
                                            {Object.entries(memory.metadata).map(([key, value]) => (
                                                <span
                                                    key={key}
                                                    className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                                                >
                                                    {key}: {String(value)}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </Link>
                    </li>
                ))}
            </ul>
        </div>
    );
};

export default MemoryList;