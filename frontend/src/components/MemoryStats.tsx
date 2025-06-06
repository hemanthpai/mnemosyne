import React from "react";

interface MemoryStatsProps {
    stats: {
        total_memories: number;
        domain_distribution: Record<string, number>;
        top_tags: Record<string, number>;
        vector_collection_info?: any;
    };
}

const MemoryStats: React.FC<MemoryStatsProps> = ({ stats }) => {
    const domainColors = {
        personal: "bg-blue-100 text-blue-800",
        professional: "bg-green-100 text-green-800",
        academic: "bg-purple-100 text-purple-800",
        creative: "bg-pink-100 text-pink-800",
    };

    // Calculate tag statistics
    const totalTags = Object.keys(stats.top_tags).length;
    const totalTagUsage = Object.values(stats.top_tags).reduce(
        (sum, count) => sum + count,
        0
    );
    const averageTagsPerMemory =
        stats.total_memories > 0
            ? (totalTagUsage / stats.total_memories).toFixed(1)
            : "0";

    return (
        <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-6">
                Memory Statistics
            </h3>

            <div className="space-y-6">
                {/* Overview Stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center p-4 bg-gray-50 rounded-lg">
                        <div className="text-2xl font-bold text-gray-900">
                            {stats.total_memories}
                        </div>
                        <div className="text-sm text-gray-600">
                            Total Memories
                        </div>
                    </div>

                    <div className="text-center p-4 bg-gray-50 rounded-lg">
                        <div className="text-2xl font-bold text-blue-600">
                            {totalTags}
                        </div>
                        <div className="text-sm text-gray-600">Unique Tags</div>
                    </div>

                    <div className="text-center p-4 bg-gray-50 rounded-lg">
                        <div className="text-2xl font-bold text-green-600">
                            {averageTagsPerMemory}
                        </div>
                        <div className="text-sm text-gray-600">
                            Avg Tags/Memory
                        </div>
                    </div>

                    <div className="text-center p-4 bg-gray-50 rounded-lg">
                        <div className="text-2xl font-bold text-purple-600">
                            {Object.keys(stats.domain_distribution).length}
                        </div>
                        <div className="text-sm text-gray-600">Domains</div>
                    </div>
                </div>

                {/* Domain Distribution */}
                {Object.keys(stats.domain_distribution).length > 0 && (
                    <div>
                        <h4 className="text-sm font-medium text-gray-900 mb-3">
                            Domain Distribution
                        </h4>
                        <div className="space-y-2">
                            {Object.entries(stats.domain_distribution)
                                .sort(([, a], [, b]) => b - a)
                                .map(([domain, count]) => {
                                    const percentage =
                                        stats.total_memories > 0
                                            ? (
                                                  (count /
                                                      stats.total_memories) *
                                                  100
                                              ).toFixed(1)
                                            : "0";

                                    return (
                                        <div
                                            key={domain}
                                            className="flex items-center justify-between"
                                        >
                                            <div className="flex items-center">
                                                <span
                                                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                                        domainColors[
                                                            domain as keyof typeof domainColors
                                                        ] ||
                                                        "bg-gray-100 text-gray-800"
                                                    }`}
                                                >
                                                    {domain}
                                                </span>
                                                <span className="ml-2 text-sm text-gray-500">
                                                    {percentage}%
                                                </span>
                                            </div>
                                            <span className="text-sm font-medium text-gray-900">
                                                {count}
                                            </span>
                                        </div>
                                    );
                                })}
                        </div>
                    </div>
                )}

                {/* Top Tags */}
                <div>
                    <h4 className="text-sm font-medium text-gray-900 mb-3">
                        Most Common Tags
                    </h4>
                    <div className="flex flex-wrap gap-2">
                        {Object.entries(stats.top_tags)
                            .sort(([, a], [, b]) => b - a)
                            .slice(0, 15)
                            .map(([tag, count]) => (
                                <span
                                    key={tag}
                                    className="inline-flex items-center px-2 py-1 rounded text-xs bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
                                    title={`Used ${count} times`}
                                >
                                    {tag} ({count})
                                </span>
                            ))}
                        {Object.keys(stats.top_tags).length > 15 && (
                            <span className="inline-flex items-center px-2 py-1 rounded text-xs bg-blue-100 text-blue-700">
                                +{Object.keys(stats.top_tags).length - 15} more
                            </span>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MemoryStats;
