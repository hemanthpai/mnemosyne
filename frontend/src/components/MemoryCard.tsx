import React from "react";
import { Memory } from "../types/index";

interface MemoryCardProps {
    memory: Memory;
}

const MemoryCard: React.FC<MemoryCardProps> = ({ memory }) => {
    const tags = memory.metadata?.tags || [];
    const confidence = memory.metadata?.confidence || 0;
    const entityType = memory.metadata?.entity_type || 'general';
    const inferenceLevel = memory.metadata?.inference_level || 'stated';
    const certainty = memory.metadata?.certainty || confidence;
    const evidence = memory.metadata?.evidence || '';
    const relationshipHints = memory.metadata?.relationship_hints || [];
    const conversationChunks = memory.conversation_chunk_ids || [];
    const hybridScore = memory.hybrid_search_score;

    // Categorize tags for better display
    const domainTags = tags.filter((tag) =>
        ["personal", "professional", "academic", "creative"].includes(
            tag.toLowerCase()
        )
    );
    const otherTags = tags.filter(
        (tag) =>
            !["personal", "professional", "academic", "creative"].includes(
                tag.toLowerCase()
            )
    );

    return (
        <div className="bg-white rounded-lg shadow-md p-6 mb-4 border border-gray-200">
            {/* Header with entity type and inference level indicators */}
            <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center space-x-2">
                    {/* Entity Type Badge */}
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                        entityType === 'person' ? 'bg-purple-100 text-purple-800' :
                        entityType === 'place' ? 'bg-green-100 text-green-800' :
                        entityType === 'preference' ? 'bg-pink-100 text-pink-800' :
                        entityType === 'skill' ? 'bg-yellow-100 text-yellow-800' :
                        entityType === 'fact' ? 'bg-blue-100 text-blue-800' :
                        entityType === 'event' ? 'bg-indigo-100 text-indigo-800' :
                        'bg-gray-100 text-gray-800'
                    }`}>
                        {entityType}
                    </span>

                    {/* Inference Level Indicator */}
                    <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                        inferenceLevel === 'stated' ? 'bg-green-50 text-green-700 border border-green-200' :
                        inferenceLevel === 'inferred' ? 'bg-yellow-50 text-yellow-700 border border-yellow-200' :
                        'bg-orange-50 text-orange-700 border border-orange-200'
                    }`}>
                        {inferenceLevel === 'stated' ? '🟢 Stated' :
                         inferenceLevel === 'inferred' ? '🟡 Inferred' : '🟠 Implied'}
                    </span>
                </div>

                {/* Hybrid Search Score */}
                {hybridScore && (
                    <div className="text-xs text-gray-500">
                        Score: {(hybridScore * 100).toFixed(1)}%
                    </div>
                )}
            </div>

            <div className="mb-4">
                <p className="text-gray-900 leading-relaxed">
                    {memory.content}
                </p>
            </div>

            {/* Tags Section */}
            <div className="mb-3">
                <div className="flex flex-wrap gap-2">
                    {/* Domain Tags with different styling */}
                    {domainTags.map((tag) => (
                        <span
                            key={tag}
                            className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                        >
                            {tag}
                        </span>
                    ))}

                    {/* Other Tags */}
                    {otherTags.map((tag) => (
                        <span
                            key={tag}
                            className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800"
                        >
                            {tag}
                        </span>
                    ))}
                </div>
            </div>

            {/* Evidence and Relationships */}
            {(evidence || relationshipHints.length > 0) && (
                <div className="mb-3 p-3 bg-gray-50 rounded border">
                    {evidence && (
                        <div className="text-sm text-gray-700 mb-2">
                            <span className="font-medium text-gray-900">Evidence:</span> {evidence}
                        </div>
                    )}
                    
                    {relationshipHints.length > 0 && (
                        <div className="text-sm">
                            <span className="font-medium text-gray-900">Relationships:</span>
                            <div className="flex flex-wrap gap-1 mt-1">
                                {relationshipHints.map((hint, index) => (
                                    <span
                                        key={index}
                                        className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                                            hint === 'contradicts' ? 'bg-red-100 text-red-700' :
                                            hint === 'updates' ? 'bg-orange-100 text-orange-700' :
                                            hint === 'supports' ? 'bg-green-100 text-green-700' :
                                            hint === 'temporal_sequence' ? 'bg-blue-100 text-blue-700' :
                                            'bg-purple-100 text-purple-700'
                                        }`}
                                    >
                                        {hint.replace('_', ' ')}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Conversation Chunks */}
            {conversationChunks.length > 0 && (
                <div className="mb-3 text-sm text-gray-600">
                    <span className="font-medium">Source conversations:</span>{" "}
                    <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded">
                        {conversationChunks.length} chunk{conversationChunks.length !== 1 ? 's' : ''}
                    </span>
                </div>
            )}

            {/* Metadata Footer */}
            <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
                <div className="flex items-center space-x-4">
                    <span className="text-xs text-gray-600">
                        <span className="font-medium">Certainty:</span>{" "}
                        {(certainty * 100).toFixed(0)}%
                    </span>
                    <span className="text-xs text-gray-600">
                        <span className="font-medium">Created:</span>{" "}
                        {new Date(memory.created_at).toLocaleDateString()}
                    </span>
                </div>

                <div className="text-xs text-gray-500">
                    ID: {memory.id.slice(0, 8)}...
                </div>
            </div>
        </div>
    );
};

export default MemoryCard;
