import React from "react";
import { Memory } from "../types/index";

interface MemoryCardProps {
    memory: Memory;
}

const MemoryCard: React.FC<MemoryCardProps> = ({ memory }) => {
    const tags = memory.metadata?.tags || [];
    const confidence = memory.metadata?.confidence || 0;
    const context = memory.metadata?.context || "";
    const connections = memory.metadata?.connections || [];

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

            {/* Context and Metadata */}
            <div className="text-sm text-gray-600 space-y-1">
                {context && (
                    <div>
                        <span className="font-medium">Context:</span> {context}
                    </div>
                )}

                {connections.length > 0 && (
                    <div>
                        <span className="font-medium">Related to:</span>{" "}
                        {connections.join(", ")}
                    </div>
                )}

                <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
                    <div className="flex items-center space-x-4">
                        <span className="text-xs">
                            <span className="font-medium">Confidence:</span>{" "}
                            {(confidence * 100).toFixed(0)}%
                        </span>
                        <span className="text-xs">
                            <span className="font-medium">Created:</span>{" "}
                            {new Date(memory.created_at).toLocaleDateString()}
                        </span>
                    </div>

                    <div className="text-xs text-gray-500">
                        ID: {memory.id.slice(0, 8)}...
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MemoryCard;
