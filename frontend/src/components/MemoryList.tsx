import React from "react";
import { Link } from "react-router-dom";
import { Memory } from "../types/index";

interface MemoryListProps {
    memories: Memory[];
}

const MemoryList: React.FC<MemoryListProps> = ({ memories }) => {
    if (memories.length === 0) {
        return (
            <div className="text-center py-12">
                <svg
                    className="mx-auto h-12 w-12 text-gray-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                </svg>
                <h3 className="mt-2 text-sm font-medium text-gray-900">
                    No memories found
                </h3>
                <p className="mt-1 text-sm text-gray-500">
                    Enter a User ID to view memories for that user.
                </p>
            </div>
        );
    }

    return (
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
            <ul className="divide-y divide-gray-200">
                {memories.map((memory) => (
                    <li key={memory.id}>
                        <Link
                            to={`/memory/${memory.id}`}
                            className="block hover:bg-gray-50"
                        >
                            <div className="px-4 py-4 sm:px-6">
                                <div className="flex items-center justify-between">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center space-x-2 mb-1">
                                            <p className="text-sm font-medium text-gray-900 truncate">
                                                {memory.content.substring(0, 80)}
                                                {memory.content.length > 80 && "..."}
                                            </p>
                                            
                                            {/* Entity Type Badge */}
                                            <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                                                memory.metadata?.entity_type === 'person' ? 'bg-purple-100 text-purple-800' :
                                                memory.metadata?.entity_type === 'place' ? 'bg-green-100 text-green-800' :
                                                memory.metadata?.entity_type === 'preference' ? 'bg-pink-100 text-pink-800' :
                                                memory.metadata?.entity_type === 'skill' ? 'bg-yellow-100 text-yellow-800' :
                                                memory.metadata?.entity_type === 'fact' ? 'bg-blue-100 text-blue-800' :
                                                memory.metadata?.entity_type === 'event' ? 'bg-indigo-100 text-indigo-800' :
                                                'bg-gray-100 text-gray-800'
                                            }`}>
                                                {memory.metadata?.entity_type || 'general'}
                                            </span>

                                            {/* Inference Level */}
                                            <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                                                memory.metadata?.inference_level === 'stated' ? 'bg-green-50 text-green-700 border border-green-200' :
                                                memory.metadata?.inference_level === 'inferred' ? 'bg-yellow-50 text-yellow-700 border border-yellow-200' :
                                                'bg-orange-50 text-orange-700 border border-orange-200'
                                            }`}>
                                                {memory.metadata?.inference_level === 'stated' ? '🟢' :
                                                 memory.metadata?.inference_level === 'inferred' ? '🟡' : '🟠'}
                                            </span>
                                        </div>
                                        
                                        <div className="flex items-center space-x-4 text-sm text-gray-500">
                                            <span>User: {memory.user_id}</span>
                                            
                                            {/* Hybrid Search Score */}
                                            {memory.hybrid_search_score && (
                                                <span className="text-xs">
                                                    Score: {(memory.hybrid_search_score * 100).toFixed(1)}%
                                                </span>
                                            )}
                                            
                                            {/* Conversation Chunks Count */}
                                            {memory.conversation_chunk_ids && memory.conversation_chunk_ids.length > 0 && (
                                                <span className="text-xs bg-blue-50 text-blue-600 px-2 py-1 rounded">
                                                    {memory.conversation_chunk_ids.length} chunk{memory.conversation_chunk_ids.length !== 1 ? 's' : ''}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex-shrink-0 text-sm text-gray-500">
                                        {new Date(memory.created_at).toLocaleDateString()}
                                    </div>
                                </div>
                                
                                {/* Tags */}
                                {memory.metadata?.tags && memory.metadata.tags.length > 0 && (
                                    <div className="mt-2">
                                        <div className="flex flex-wrap gap-1">
                                            {memory.metadata.tags.slice(0, 5).map((tag, index) => (
                                                <span
                                                    key={index}
                                                    className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800"
                                                >
                                                    {tag}
                                                </span>
                                            ))}
                                            {memory.metadata.tags.length > 5 && (
                                                <span className="text-xs text-gray-500">
                                                    +{memory.metadata.tags.length - 5} more
                                                </span>
                                            )}
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
