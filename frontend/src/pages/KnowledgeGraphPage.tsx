import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { GraphCanvas, GraphNode as ReagraphNode, GraphEdge as ReagraphEdge, lightTheme, darkTheme } from 'reagraph';
import PageHeader from '../components/PageHeader';
import { useTheme } from '../contexts/ThemeContext';
import { useSidebar } from '../contexts/SidebarContext';

// Auto-detect API base URL
const getApiBaseUrl = (): string => {
  if (typeof window === 'undefined') {
    return 'http://localhost:8000';
  }
  return '';
};

const API_BASE_URL = getApiBaseUrl();

interface GraphNode {
  id: string;
  content: string;
  note_type: string;
  confidence: number;
  importance_score: number;
  tags: string[];
  relationship_count: number;
  created_at: string;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  strength: number;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    total_nodes: number;
    total_edges: number;
    note_types: Record<string, number>;
  };
}

// Dynamic color generation for note types
const getNoteTypeColor = (noteType: string): string => {
  // Base colors for each category prefix
  const categoryBaseColors: Record<string, { hue: number; saturation: number; lightness: number }> = {
    'interest': { hue: 217, saturation: 91, lightness: 60 },   // blue
    'goal': { hue: 262, saturation: 83, lightness: 58 },       // purple
    'skill': { hue: 142, saturation: 76, lightness: 45 },      // green
    'preference': { hue: 38, saturation: 92, lightness: 50 },  // orange
    'personal': { hue: 189, saturation: 94, lightness: 43 },   // cyan
  };

  const [prefix, suffix] = noteType.split(':');
  const baseColor = categoryBaseColors[prefix] || { hue: 220, saturation: 9, lightness: 46 }; // gray fallback

  // If no suffix, just return the base color
  if (!suffix) {
    return `hsl(${baseColor.hue}, ${baseColor.saturation}%, ${baseColor.lightness}%)`;
  }

  // Generate a deterministic hash from the suffix to create color variations
  let hash = 0;
  for (let i = 0; i < suffix.length; i++) {
    hash = ((hash << 5) - hash) + suffix.charCodeAt(i);
    hash = hash & hash; // Convert to 32-bit integer
  }

  // Create variations within the same hue family
  const hueVariation = (Math.abs(hash) % 30) - 15; // ±15 degree variation
  const satVariation = (Math.abs(hash >> 8) % 20) - 10; // ±10% saturation
  const lightVariation = (Math.abs(hash >> 16) % 20) - 10; // ±10% lightness

  const finalHue = (baseColor.hue + hueVariation + 360) % 360;
  const finalSat = Math.max(40, Math.min(100, baseColor.saturation + satVariation));
  const finalLight = Math.max(35, Math.min(65, baseColor.lightness + lightVariation));

  return `hsl(${finalHue}, ${finalSat}%, ${finalLight}%)`;
};

const KnowledgeGraphPage: React.FC = () => {
  const { theme } = useTheme();
  const { isSidebarOpen } = useSidebar();
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // Filters
  const [noteTypeFilter, setNoteTypeFilter] = useState<string>('');
  const [limit, setLimit] = useState<number | 'all'>(100);
  const [minStrength, setMinStrength] = useState(0.5);
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [showLegend, setShowLegend] = useState(true);

  // User management
  const [availableUsers, setAvailableUsers] = useState<Array<{ id: string; name: string }>>([]);
  const [userId, setUserId] = useState(sessionStorage.getItem('user_id') || '');

  // Fetch available users on mount
  useEffect(() => {
    const loadUsers = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/notes/users/`);
        const data = await response.json();

        if (data.success && data.users.length > 0) {
          // Map users to format expected by dropdown
          const users = data.users.map((u: { user_id: string; note_count: number }) => ({
            id: u.user_id,
            name: `User ${u.user_id.substring(0, 8)} (${u.note_count} notes)`
          }));
          setAvailableUsers(users);

          // Set initial userId if not already set
          if (!userId) {
            const firstUserId = users[0].id;
            setUserId(firstUserId);
            sessionStorage.setItem('user_id', firstUserId);
          }
        }
      } catch (err) {
        console.error('Failed to load users:', err);
      }
    };

    loadUsers();
  }, []);

  const fetchGraphData = useCallback(async () => {
    // Don't fetch if no user selected yet
    if (!userId) return;

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        user_id: userId,
        limit: limit === 'all' ? '10000' : limit.toString(), // Use a high number for "all"
        min_strength: minStrength.toString(),
      });

      if (noteTypeFilter) {
        params.append('note_type', noteTypeFilter);
      }

      const response = await fetch(
        `${API_BASE_URL}/api/notes/graph/?${params.toString()}`
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || 'Failed to fetch graph data');
      }

      setGraphData(data);
    } catch (err) {
      console.error('Error fetching graph data:', err);
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
    } finally {
      setLoading(false);
    }
  }, [userId, noteTypeFilter, limit, minStrength]);

  useEffect(() => {
    fetchGraphData();
  }, [fetchGraphData]);

  const handleNodeClick = useCallback((node: ReagraphNode | null) => {
    if (node && graphData) {
      const fullNode = graphData.nodes.find(n => n.id === node.id);
      setSelectedNode(fullNode || null);
    } else {
      setSelectedNode(null);
    }
  }, [graphData]);

  // Transform data for Reagraph
  const reagraphData = useMemo(() => {
    if (!graphData) return { nodes: [], edges: [] };

    const nodes: ReagraphNode[] = graphData.nodes.map((n) => ({
      id: n.id,
      label: n.content.substring(0, 50) + (n.content.length > 50 ? '...' : ''),
      fill: getNoteTypeColor(n.note_type),
      size: Math.max(n.importance_score * 3, 5),
    }));

    const edges: ReagraphEdge[] = graphData.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.relationship_type,
      size: e.strength * 2,
    }));

    return { nodes, edges };
  }, [graphData]);

  // Get unique note types for filter dropdown
  const availableNoteTypes = graphData
    ? Object.keys(graphData.stats.note_types).sort()
    : [];

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-300 text-lg">Loading knowledge graph...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="bg-white dark:bg-gray-800 shadow-lg rounded-lg p-8 max-w-md w-full">
          <div className="text-center">
            <div className="text-6xl mb-4">⚠️</div>
            <h2 className="text-2xl font-bold text-gray-800 dark:text-gray-100 mb-4">Error Loading Graph</h2>
            <p className="text-red-600 dark:text-red-400 mb-6">{error}</p>
            <button
              onClick={fetchGraphData}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="bg-white dark:bg-gray-800 shadow-lg rounded-lg p-8 max-w-md w-full text-center">
          <div className="text-6xl mb-4">📊</div>
          <h2 className="text-2xl font-bold text-gray-800 dark:text-gray-100 mb-4">No Knowledge Graph Yet</h2>
          <p className="text-gray-600 dark:text-gray-300 mb-6">
            Start having conversations and the system will automatically extract and build your knowledge graph.
          </p>
          <a
            href="/devtools"
            className="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Go to DevTools
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
      <PageHeader
        title="Knowledge Graph"
        subtitle="Interactive visualization of your knowledge graph showing atomic notes and their relationships"
        badge={{ text: `${graphData.stats.total_nodes.toLocaleString()} nodes`, color: "blue" }}
      />

      <div className={`transition-all duration-300 ${isSidebarOpen ? 'ml-60' : 'ml-0'} flex-1 flex flex-col`}>
      {/* Filters */}
      <div className="bg-white dark:bg-gray-800 shadow-sm border-b dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 sm:py-4">
          {/* Primary filters row - always visible */}
          <div className="flex gap-3 items-end flex-wrap">
            <div className="flex-1 min-w-[200px] sm:w-60 sm:flex-initial">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                User
              </label>
              <select
                value={userId}
                onChange={(e) => {
                  const newUserId = e.target.value;
                  setUserId(newUserId);
                  sessionStorage.setItem('user_id', newUserId);
                }}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 dark:text-gray-100 text-sm"
              >
                {availableUsers.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Advanced Filters Toggle Button */}
            <button
              onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
              className="flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
              Filters
              <svg className={`w-4 h-4 transition-transform ${showAdvancedFilters ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Legend Toggle Button (Mobile/Tablet) */}
            <button
              onClick={() => setShowLegend(!showLegend)}
              className="lg:hidden flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm font-medium text-gray-700"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
              </svg>
              Legend
            </button>

            <button
              onClick={fetchGraphData}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
            >
              Refresh
            </button>
          </div>

          {/* Advanced filters - collapsible */}
          {showAdvancedFilters && (
            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Filter by Note Type
                  </label>
                  <select
                    value={noteTypeFilter}
                    onChange={(e) => setNoteTypeFilter(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-gray-100 text-sm"
                  >
                    <option value="">All Types ({graphData.nodes.length} nodes)</option>
                    {availableNoteTypes.map((type) => (
                      <option key={type} value={type}>
                        {type} ({graphData.stats.note_types[type]})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Node Limit
                  </label>
                  <select
                    value={limit}
                    onChange={(e) => setLimit(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-gray-100 text-sm"
                  >
                    <option value="50">50 nodes</option>
                    <option value="100">100 nodes</option>
                    <option value="200">200 nodes</option>
                    <option value="500">500 nodes</option>
                    <option value="1000">1,000 nodes</option>
                    <option value="all">All nodes</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Min Relationship Strength
                  </label>
                  <select
                    value={minStrength}
                    onChange={(e) => setMinStrength(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-gray-100 text-sm"
                  >
                    <option value="0.3">0.3 (More connections)</option>
                    <option value="0.5">0.5 (Balanced)</option>
                    <option value="0.7">0.7 (Strong)</option>
                    <option value="0.9">0.9 (Very strong)</option>
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Graph Visualization */}
      <div className="flex-1 flex">
        <div className="flex-1 relative">
          <GraphCanvas
            nodes={reagraphData.nodes}
            edges={reagraphData.edges}
            onNodeClick={handleNodeClick}
            theme={theme === 'dark' ? {
              ...darkTheme,
              canvas: { background: '#111827' },
            } : {
              ...lightTheme,
              canvas: { background: '#f9fafb' },
            }}
            draggable
            layoutType="forceDirected2d"
          />

          {/* Legend Toggle Button (Desktop only, floating) */}
          {!selectedNode && !showLegend && (
            <button
              onClick={() => setShowLegend(true)}
              className="hidden lg:flex absolute top-4 right-4 items-center gap-2 px-3 py-2 bg-white dark:bg-gray-800 shadow-lg rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-sm font-medium text-gray-700 dark:text-gray-300 z-10"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
              </svg>
              Legend
            </button>
          )}

          {/* Legend */}
          {!selectedNode && showLegend && (
            <div className="absolute bottom-4 right-4 bg-white dark:bg-gray-800 shadow-lg rounded-lg p-4 max-w-xs lg:max-w-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Legend</h3>
                <button
                  onClick={() => setShowLegend(false)}
                  className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                  aria-label="Close legend"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <div className="space-y-2 max-h-48 lg:max-h-64 overflow-y-auto">
                {Object.entries(graphData.stats.note_types)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 10)
                  .map(([type, count]) => (
                    <div key={type} className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full flex-shrink-0"
                        style={{ backgroundColor: getNoteTypeColor(type) }}
                      />
                      <span className="text-xs text-gray-700 dark:text-gray-300 flex-1 truncate">{type}</span>
                      <span className="text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">{count}</span>
                    </div>
                  ))}
              </div>
              <div className="mt-3 pt-3 border-t dark:border-gray-700 space-y-1">
                <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">How to use:</p>
                <p className="text-xs text-gray-600 dark:text-gray-400">• Scroll to zoom in/out</p>
                <p className="text-xs text-gray-600 dark:text-gray-400">• Click and drag to pan</p>
                <p className="text-xs text-gray-600 dark:text-gray-400">• Click nodes for details</p>
                <div className="mt-2 pt-2 border-t dark:border-gray-700">
                  <p className="text-xs text-gray-500 dark:text-gray-400">Node size = importance</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Edge size = strength</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Node Details Panel - Responsive width */}
        {selectedNode && (
          <div className="w-full sm:w-80 lg:w-96 bg-white dark:bg-gray-800 shadow-xl border-l dark:border-gray-700 overflow-y-auto">
            <div className="p-4 sm:p-6">
              <div className="flex items-start justify-between mb-4">
                <div
                  className="w-4 h-4 rounded-full mt-1"
                  style={{ backgroundColor: getNoteTypeColor(selectedNode.note_type) }}
                />
                <button
                  onClick={() => setSelectedNode(null)}
                  className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
                    Content
                  </label>
                  <p className="text-gray-900 dark:text-gray-100">{selectedNode.content}</p>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
                    Type
                  </label>
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200">
                    {selectedNode.note_type}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
                      Confidence
                    </label>
                    <p className="text-gray-900 dark:text-gray-100">{(selectedNode.confidence * 100).toFixed(0)}%</p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
                      Importance
                    </label>
                    <p className="text-gray-900 dark:text-gray-100">{selectedNode.importance_score.toFixed(2)}</p>
                  </div>
                </div>

                {selectedNode.tags.length > 0 && (
                  <div>
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
                      Tags
                    </label>
                    <div className="flex flex-wrap gap-1">
                      {selectedNode.tags.map((tag, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
                    Relationships
                  </label>
                  <p className="text-gray-900 dark:text-gray-100">{selectedNode.relationship_count} connections</p>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
                    Created
                  </label>
                  <p className="text-gray-900 dark:text-gray-100 text-sm">
                    {new Date(selectedNode.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
      </div>
    </div>
  );
};

export default KnowledgeGraphPage;
