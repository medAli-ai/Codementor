// ============================================================
// DocumentLibrary.jsx
// ============================================================
// Matches existing design language:
//   - bg-gray-100 page background
//   - bg-gray-900 sidebar
//   - bg-white cards with border-gray-200
//   - blue-600 accents + buttons
//
// Polling: every 5s while any doc is processing, silent re-fetch
// Delete: optimistic removal with restore on error
// URL params: topic + status + page synced to URL
// ============================================================

import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { documentsAPI, DOCUMENT_TOPICS, DOCUMENT_STATUSES } from '../services/api';
import DocumentUpload from '../components/DocumentUpload';

const PAGE_SIZE      = 12;
const POLL_INTERVAL  = 5000;

// ── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }) {
  const config = {
    processing: { emoji: '⏳', className: 'bg-amber-100 text-amber-700',   pulse: true  },
    completed:  { emoji: '✅', className: 'bg-green-100 text-green-700',   pulse: false },
    failed:     { emoji: '❌', className: 'bg-red-100 text-red-600',       pulse: false },
  }[status] ?? { emoji: '❓', className: 'bg-gray-100 text-gray-600', pulse: false };

  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${config.className}`}>
      {config.pulse && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-amber-500" />
        </span>
      )}
      {config.emoji} {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

// ── Document card ─────────────────────────────────────────────────────────────
function DocumentCard({ doc, onDelete }) {
  const [confirming, setConfirming] = useState(false);
  const [deleting,   setDeleting]   = useState(false);

  const topicLabel = DOCUMENT_TOPICS.find(t => t.value === doc.topic)?.label ?? doc.topic;

  const handleDelete = async () => {
    setDeleting(true);
    await onDelete(doc.id);
    // No need to reset — card is removed from DOM on success
  };

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-4 shadow-sm hover:shadow-md transition-shadow flex flex-col">
      {/* Topic + status row */}
      <div className="flex items-center justify-between mb-3">
        <span className="bg-blue-50 text-blue-600 text-xs font-medium px-2.5 py-0.5 rounded-full">
          {topicLabel}
        </span>
        <StatusBadge status={doc.status} />
      </div>

      {/* Title */}
      <h3 className="text-sm font-semibold text-gray-800 line-clamp-2 mb-2">
        {doc.title}
      </h3>

      {/* Meta */}
      <div className="flex items-center gap-3 text-xs text-gray-400 mt-auto pt-2">
        {doc.chunks_count != null && (
          <span>🧩 {doc.chunks_count} chunks</span>
        )}
        <span>
          {new Date(doc.created_at).toLocaleDateString('en-US', {
            month: 'short', day: 'numeric', year: 'numeric',
          })}
        </span>
        {doc.is_public && <span className="ml-auto">🌐 Public</span>}
      </div>

      {/* Delete */}
      <div className="mt-3 border-t border-gray-100 pt-3">
        {!confirming ? (
          <button
            onClick={() => setConfirming(true)}
            className="w-full text-xs text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg py-1.5 transition-colors"
          >
            🗑️ Delete
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={() => setConfirming(false)}
              disabled={deleting}
              className="flex-1 border border-gray-200 rounded-lg py-1.5 text-xs text-gray-600 hover:bg-gray-50"
            >Cancel</button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="flex-1 bg-red-600 text-white rounded-lg py-1.5 text-xs font-medium hover:bg-red-700 disabled:opacity-50"
            >
              {deleting ? 'Deleting…' : 'Confirm'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Skeleton card ─────────────────────────────────────────────────────────────
function SkeletonCard() {
  return (
    <div className="bg-white border border-gray-100 rounded-2xl p-4 animate-pulse">
      <div className="flex justify-between mb-3">
        <div className="h-5 w-16 bg-gray-100 rounded-full" />
        <div className="h-5 w-20 bg-gray-100 rounded-full" />
      </div>
      <div className="h-4 w-3/4 bg-gray-100 rounded mb-2" />
      <div className="h-4 w-1/2 bg-gray-100 rounded" />
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────
function EmptyState({ hasFilters, onUpload }) {
  return (
    <div className="col-span-full flex flex-col items-center justify-center py-20 text-center">
      <div className="text-5xl mb-4">📭</div>
      {hasFilters ? (
        <>
          <p className="text-gray-600 font-medium">No documents match your filters</p>
          <p className="text-gray-400 text-sm mt-1">Try clearing topic or status.</p>
        </>
      ) : (
        <>
          <p className="text-gray-600 font-medium">Your library is empty</p>
          <p className="text-gray-400 text-sm mt-1">Upload your first PDF to get personalized answers.</p>
          <button
            onClick={onUpload}
            className="mt-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl px-5 py-2 text-sm font-semibold"
          >
            Upload your first document
          </button>
        </>
      )}
    </div>
  );
}

// ── Pagination ────────────────────────────────────────────────────────────────
function Pagination({ page, totalPages, onPage }) {
  if (totalPages <= 1) return null;
  return (
    <div className="mt-8 flex items-center justify-center gap-3">
      <button
        onClick={() => onPage(page - 1)}
        disabled={page <= 1}
        className="border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-40"
      >← Prev</button>
      <span className="text-sm text-gray-500">Page {page} of {totalPages}</span>
      <button
        onClick={() => onPage(page + 1)}
        disabled={page >= totalPages}
        className="border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-40"
      >Next →</button>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function DocumentLibrary() {
  const { user, logout } = useAuth();
  const navigate         = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Filters synced to URL
  const topicFilter  = searchParams.get('topic')  ?? '';
  const statusFilter = searchParams.get('status') ?? '';
  const currentPage  = parseInt(searchParams.get('page') ?? '1', 10);

  const setFilter = (key, value) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      value ? next.set(key, value) : next.delete(key);
      next.set('page', '1');
      return next;
    });
  };

  const setPage = (p) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      next.set('page', String(p));
      return next;
    });
  };

  // Data
  const [documents,  setDocuments]  = useState([]);
  const [total,      setTotal]      = useState(0);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState(null);
  const [showUpload, setShowUpload] = useState(false);

  const pollRef = useRef(null);

  const fetchDocuments = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const res = await documentsAPI.list({
        topic: topicFilter, status: statusFilter,
        page: currentPage,  page_size: PAGE_SIZE,
      });
      setDocuments(res.data.documents);
      setTotal(res.data.total);
    } catch {
      setError('Failed to load documents. Please refresh.');
    } finally {
      setLoading(false);
    }
  }, [topicFilter, statusFilter, currentPage]);

  // Fetch on filter/page change
  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  // Poll while any doc is processing
  useEffect(() => {
    const hasProcessing = documents.some(d => d.status === 'processing');
    if (hasProcessing) {
      pollRef.current = setInterval(() => fetchDocuments(true), POLL_INTERVAL);
    }
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [documents, fetchDocuments]);

  // Optimistic delete
  const handleDelete = async (id) => {
    const previous = documents;
    setDocuments(docs => docs.filter(d => d.id !== id));
    setTotal(t => t - 1);
    try {
      await documentsAPI.delete(id);
    } catch {
      setDocuments(previous);
      setTotal(t => t + 1);
      setError('Delete failed. Please try again.');
    }
  };

  const handleUploadSuccess = () => {
    setShowUpload(false);
    fetchDocuments();
  };

  const totalPages      = Math.ceil(total / PAGE_SIZE);
  const hasFilters      = !!(topicFilter || statusFilter);
  const processingCount = documents.filter(d => d.status === 'processing').length;

  return (
    <div className="flex h-screen bg-gray-100">

      {/* ===== SIDEBAR — matches Chat.jsx exactly ===== */}
      <div className="w-64 bg-gray-900 text-white flex flex-col">

        <div className="p-4 border-b border-gray-700">
          <h1 className="text-xl font-bold text-blue-400">🎓 CodeMentor</h1>
          <p className="text-gray-400 text-sm">AI Coding Tutor</p>
        </div>

        <div className="p-3 space-y-2">
         

          <button
    onClick={() => {
      const lastId = sessionStorage.getItem('lastConversationId');
      navigate(lastId ? `/chat/${lastId}` : '/chat');
    }}
    className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2 px-4 text-sm font-medium transition-colors"
  >
    💬 Go to Chat
  </button>

          <button
            onClick={() => setShowUpload(true)}
            className="w-full bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg py-2 px-4 text-sm font-medium transition-colors"
          >
            + Upload Document
          </button>
        </div>

        <div className="flex-1" />

        <div className="p-4 border-t border-gray-700">
          <p className="text-gray-400 text-sm truncate mb-2">👤 {user?.username}</p>
          <button
            onClick={logout}
            className="w-full text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg py-2 px-4 text-sm transition-colors text-left"
          >
            🚪 Logout
          </button>
        </div>
      </div>

      {/* ===== MAIN CONTENT ===== */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="bg-white border-b px-6 py-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-gray-800">
                📚 My Library
                {processingCount > 0 && (
                  <span className="ml-2 text-sm text-amber-600 font-normal">
                    ⏳ {processingCount} processing…
                  </span>
                )}
              </h2>
              <p className="text-gray-400 text-sm">
                {total > 0 ? `${total} document${total !== 1 ? 's' : ''}` : 'No documents yet'}
              </p>
            </div>
            <button
              onClick={() => setShowUpload(true)}
              className="bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2 px-4 text-sm font-medium transition-colors"
            >
              + Upload Document
            </button>
          </div>

          {/* Filters */}
          <div className="mt-3 flex flex-wrap gap-2">
            <select
              value={topicFilter}
              onChange={e => setFilter('topic', e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="">All topics</option>
              {DOCUMENT_TOPICS.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>

            <select
              value={statusFilter}
              onChange={e => setFilter('status', e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="">All statuses</option>
              {DOCUMENT_STATUSES.map(s => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>

            {hasFilters && (
              <button
                onClick={() => { setFilter('topic', ''); setFilter('status', ''); }}
                className="text-sm text-gray-500 hover:text-gray-700 px-2"
              >
                Clear filters ×
              </button>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-4 py-3 text-sm mb-4 flex items-center justify-between">
              {error}
              <button onClick={() => setError(null)} className="ml-3 text-red-400 hover:text-red-600">×</button>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {loading
              ? Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)
              : documents.length === 0
              ? <EmptyState hasFilters={hasFilters} onUpload={() => setShowUpload(true)} />
              : documents.map(doc => (
                  <DocumentCard key={doc.id} doc={doc} onDelete={handleDelete} />
                ))
            }
          </div>

          {!loading && (
            <Pagination page={currentPage} totalPages={totalPages} onPage={setPage} />
          )}
        </div>
      </div>

      {/* ===== Upload modal ===== */}
      {showUpload && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={e => { if (e.target === e.currentTarget) setShowUpload(false); }}
        >
          <DocumentUpload
            onSuccess={handleUploadSuccess}
            onCancel={() => setShowUpload(false)}
          />
        </div>
      )}
    </div>
  );
}