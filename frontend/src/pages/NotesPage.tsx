import React, { useState, useEffect } from 'react';
import PageHeader from '../components/PageHeader';
import Dropdown from '../components/Dropdown';

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

  // Load note types
  useEffect(() => {
    if (!userId) return; // Don't load if no user selected yet

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
    if (!userId) return; // Don't load if no user selected yet

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
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <PageHeader
        title="Atomic Notes"
        subtitle="View and manage extracted knowledge from your conversations"
        badge={total > 0 ? { text: `${total.toLocaleString()} notes`, color: "green" } : undefined}
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

        {/* Filters */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md mb-6">
          <div className="p-4 space-y-4">
            {/* First Row: User, Search, Type */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-3">
              {/* User Selection */}
              <div className="lg:col-span-2">
                <label htmlFor="filter-user" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  User
                </label>
                <Dropdown
                  id="filter-user"
                  value={userId}
                  options={availableUsers.map(user => ({ value: user.id, label: user.name }))}
                  onChange={(newUserId) => {
                    setUserId(newUserId);
                    sessionStorage.setItem('user_id', newUserId);
                    setOffset(0);
                  }}
                  className="text-sm"
                />
              </div>

              {/* Search */}
              <div className="sm:col-span-2 lg:col-span-7">
                <label htmlFor="filter-search" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Search
                </label>
                <input
                  id="filter-search"
                  type="text"
                  value={searchTerm}
                  onChange={(e) => {
                    setSearchTerm(e.target.value);
                    setOffset(0);
                  }}
                  placeholder="Search in content, context, or tags..."
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
              </div>

              {/* Note Type Filter */}
              <div className="lg:col-span-3">
                <label htmlFor="filter-type" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Type
                </label>
                <Dropdown
                  id="filter-type"
                  value={selectedType}
                  options={[
                    { value: '', label: 'All Types' },
                    ...noteTypes.map(nt => ({ value: nt.note_type, label: `${nt.note_type} (${nt.count})` }))
                  ]}
                  onChange={(value) => {
                    setSelectedType(value);
                    setOffset(0);
                  }}
                  className="text-sm"
                />
              </div>
            </div>

            {/* Second Row: Sort By and Order */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-12 gap-3">
              {/* Sort By */}
              <div className="col-span-2 sm:col-span-1 lg:col-span-3">
                <label htmlFor="filter-sortby" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Sort By
                </label>
                <Dropdown
                  id="filter-sortby"
                  value={orderBy}
                  options={[
                    { value: 'importance_score', label: 'Importance' },
                    { value: 'created_at', label: 'Date' },
                    { value: 'confidence', label: 'Confidence' },
                    { value: 'content', label: 'Content' }
                  ]}
                  onChange={setOrderBy}
                  className="text-sm"
                />
              </div>

              {/* Sort Order */}
              <div className="col-span-2 sm:col-span-1 lg:col-span-2">
                <label htmlFor="filter-order" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Order
                </label>
                <Dropdown
                  id="filter-order"
                  value={order}
                  options={[
                    { value: 'desc', label: 'Descending ↓' },
                    { value: 'asc', label: 'Ascending ↑' }
                  ]}
                  onChange={(value) => setOrder(value as 'asc' | 'desc')}
                  className="text-sm"
                />
              </div>

              {/* Stats */}
              <div className="col-span-2 sm:col-span-1 lg:col-span-7 flex items-end">
                <p className="text-sm text-gray-600 dark:text-gray-400 pb-2">
                  Showing <span className="font-semibold">{notes.length}</span> of <span className="font-semibold">{total.toLocaleString()}</span> notes
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Top Pagination */}
        {!loading && total > limit && (
          <div className="mb-4 flex justify-center gap-2">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:hover:bg-gray-600 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 transition-colors"
            >
              ← Previous
            </button>
            <span className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400">
              Page {Math.floor(offset / limit) + 1} of {Math.ceil(total / limit)}
            </span>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:hover:bg-gray-600 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 transition-colors"
            >
              Next →
            </button>
          </div>
        )}

        {/* Loading / Error States */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 dark:border-gray-100"></div>
            <p className="mt-2 text-gray-600 dark:text-gray-400">Loading notes...</p>
          </div>
        )}

        {error && !loading && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6">
            <p className="text-red-800 dark:text-red-300">{error}</p>
          </div>
        )}

        {/* Notes List */}
        {!loading && !error && notes.length === 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-12 text-center">
            <p className="text-gray-600 dark:text-gray-300">No notes found</p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              Notes will appear here after conversations are processed
            </p>
          </div>
        )}

        {!loading && !error && notes.length > 0 && (
          <div className="space-y-3 sm:space-y-4">
            {notes.map((note) => (
              <div
                key={note.id}
                className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 sm:p-6 hover:shadow-lg transition-shadow"
              >
                {/* Header */}
                <div className="flex justify-between items-start mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`text-xs px-2 py-1 rounded-full font-medium ${getTypeColor(note.note_type)}`}>
                        {note.note_type}
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        Confidence: {(note.confidence * 100).toFixed(0)}%
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        Importance: {note.importance_score.toFixed(2)}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(note.id)}
                    className="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 text-sm"
                  >
                    Delete
                  </button>
                </div>

                {/* Content */}
                <p className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
                  {note.content}
                </p>

                {/* Context */}
                {note.context && (
                  <p className="text-sm text-gray-600 dark:text-gray-300 mb-3">
                    <span className="font-medium">Context:</span> {note.context}
                  </p>
                )}

                {/* Tags */}
                {note.tags && note.tags.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-3">
                    {note.tags.map((tag, idx) => (
                      <span
                        key={idx}
                        className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-2 py-1 rounded-full"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Footer */}
                <div className="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400 pt-3 border-t border-gray-100 dark:border-gray-700">
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
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:hover:bg-gray-600 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              Previous
            </button>
            <span className="px-4 py-2 text-gray-600 dark:text-gray-400">
              Page {Math.floor(offset / limit) + 1} of {Math.ceil(total / limit)}
            </span>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:hover:bg-gray-600 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
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
