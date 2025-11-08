import React, { useState, useEffect } from 'react';

// Auto-detect API base URL
const getApiBaseUrl = (): string => {
  if (typeof window === 'undefined') {
    return 'http://localhost:8000';
  }
  return '';
};

const API_BASE_URL = getApiBaseUrl();

interface AtomicNote {
  id: string;
  content: string;
  note_type: string;
  context: string;
  confidence: number;
  importance_score: number;
  tags: string[];
  relationships: {
    outgoing: number;
    incoming: number;
  };
  source_turn_id: string | null;
  created_at: string;
  updated_at: string;
}

interface NoteType {
  note_type: string;
  count: number;
}

const NotesPage: React.FC = () => {
  const [notes, setNotes] = useState<AtomicNote[]>([]);
  const [noteTypes, setNoteTypes] = useState<NoteType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedType, setSelectedType] = useState('');
  const [orderBy, setOrderBy] = useState('importance_score');
  const [order, setOrder] = useState('desc');

  // Pagination
  const [total, setTotal] = useState(0);
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);

  // Get user ID from session storage
  const userId = sessionStorage.getItem('user_id') || '00000000-0000-0000-0000-000000000001';

  // Load note types
  useEffect(() => {
    const loadNoteTypes = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/notes/types/?user_id=${userId}`);
        const data = await response.json();

        if (data.success) {
          setNoteTypes(data.note_types);
        }
      } catch (err) {
        console.error('Failed to load note types:', err);
      }
    };

    loadNoteTypes();
  }, [userId]);

  // Load notes
  useEffect(() => {
    const loadNotes = async () => {
      setLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          user_id: userId,
          limit: limit.toString(),
          offset: offset.toString(),
          order_by: orderBy,
          order: order
        });

        if (searchTerm) params.append('search', searchTerm);
        if (selectedType) params.append('note_type', selectedType);

        const response = await fetch(`${API_BASE_URL}/api/notes/list/?${params}`);
        const data = await response.json();

        if (data.success) {
          setNotes(data.notes);
          setTotal(data.total);
        } else {
          setError(data.error || 'Failed to load notes');
        }
      } catch (err) {
        setError('Network error loading notes');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadNotes();
  }, [userId, searchTerm, selectedType, orderBy, order, offset, limit]);

  const handleDelete = async (noteId: string) => {
    if (!confirm('Are you sure you want to delete this note?')) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/notes/delete/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ note_id: noteId }),
      });

      const data = await response.json();

      if (data.success) {
        // Refresh the list
        setNotes(notes.filter(n => n.id !== noteId));
        setTotal(total - 1);
      } else {
        alert(`Failed to delete note: ${data.error}`);
      }
    } catch (err) {
      alert('Network error deleting note');
      console.error(err);
    }
  };

  const getTypeColor = (noteType: string): string => {
    if (noteType.startsWith('preference:')) return 'bg-blue-100 text-blue-800';
    if (noteType.startsWith('skill:')) return 'bg-green-100 text-green-800';
    if (noteType.startsWith('interest:')) return 'bg-purple-100 text-purple-800';
    if (noteType.startsWith('personal:')) return 'bg-yellow-100 text-yellow-800';
    if (noteType.startsWith('goal:')) return 'bg-red-100 text-red-800';
    return 'bg-gray-100 text-gray-800';
  };

  const formatDate = (isoString: string): string => {
    const date = new Date(isoString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Atomic Notes</h1>
          <p className="text-gray-600">
            View and manage extracted knowledge from your conversations
          </p>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow-md p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Search */}
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Search
              </label>
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setOffset(0); // Reset to first page
                }}
                placeholder="Search in content, context, or tags..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Note Type Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Type
              </label>
              <select
                value={selectedType}
                onChange={(e) => {
                  setSelectedType(e.target.value);
                  setOffset(0);
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Types</option>
                {noteTypes.map(nt => (
                  <option key={nt.note_type} value={nt.note_type}>
                    {nt.note_type} ({nt.count})
                  </option>
                ))}
              </select>
            </div>

            {/* Sort By */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Sort By
              </label>
              <div className="flex gap-2">
                <select
                  value={orderBy}
                  onChange={(e) => setOrderBy(e.target.value)}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="importance_score">Importance</option>
                  <option value="created_at">Date</option>
                  <option value="confidence">Confidence</option>
                  <option value="content">Content</option>
                </select>
                <button
                  onClick={() => setOrder(order === 'asc' ? 'desc' : 'asc')}
                  className="px-3 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
                  title={order === 'asc' ? 'Ascending' : 'Descending'}
                >
                  {order === 'asc' ? '↑' : '↓'}
                </button>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-sm text-gray-600">
              Showing {notes.length} of {total} notes
            </p>
          </div>
        </div>

        {/* Loading / Error States */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
            <p className="mt-2 text-gray-600">Loading notes...</p>
          </div>
        )}

        {error && !loading && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {/* Notes List */}
        {!loading && !error && notes.length === 0 && (
          <div className="bg-white rounded-lg shadow-md p-12 text-center">
            <p className="text-gray-600">No notes found</p>
            <p className="text-sm text-gray-500 mt-2">
              Notes will appear here after conversations are processed
            </p>
          </div>
        )}

        {!loading && !error && notes.length > 0 && (
          <div className="space-y-4">
            {notes.map((note) => (
              <div
                key={note.id}
                className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow"
              >
                {/* Header */}
                <div className="flex justify-between items-start mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`text-xs px-2 py-1 rounded-full font-medium ${getTypeColor(note.note_type)}`}>
                        {note.note_type}
                      </span>
                      <span className="text-xs text-gray-500">
                        Confidence: {(note.confidence * 100).toFixed(0)}%
                      </span>
                      <span className="text-xs text-gray-500">
                        Importance: {note.importance_score.toFixed(2)}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(note.id)}
                    className="text-red-600 hover:text-red-800 text-sm"
                  >
                    Delete
                  </button>
                </div>

                {/* Content */}
                <p className="text-lg font-medium text-gray-900 mb-2">
                  {note.content}
                </p>

                {/* Context */}
                {note.context && (
                  <p className="text-sm text-gray-600 mb-3">
                    <span className="font-medium">Context:</span> {note.context}
                  </p>
                )}

                {/* Tags */}
                {note.tags && note.tags.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-3">
                    {note.tags.map((tag, idx) => (
                      <span
                        key={idx}
                        className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Footer */}
                <div className="flex justify-between items-center text-xs text-gray-500 pt-3 border-t border-gray-100">
                  <div>
                    <span>Relationships: </span>
                    <span className="font-medium">
                      {note.relationships.outgoing} outgoing, {note.relationships.incoming} incoming
                    </span>
                  </div>
                  <div>
                    Created {formatDate(note.created_at)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {!loading && total > limit && (
          <div className="mt-6 flex justify-center gap-2">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="px-4 py-2 border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              Previous
            </button>
            <span className="px-4 py-2 text-gray-600">
              Page {Math.floor(offset / limit) + 1} of {Math.ceil(total / limit)}
            </span>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
              className="px-4 py-2 border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default NotesPage;
