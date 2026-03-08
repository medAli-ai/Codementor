import { useEffect, useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useChunkPreview } from '../context/useChunkPreview';
import { chunkPreviewAPI } from '../services/api';

// ── Chunk type badge — same colours as SearchModal / SourceCitations ──────────
const CHUNK_BADGE = {
  code:  { label: '</> code',  color: '#6366f1' },
  table: { label: '⊞ table',  color: '#0891b2' },
  prose: { label: '¶ prose',  color: '#059669' },
};

function ChunkBadge({ type }) {
  const badge = CHUNK_BADGE[type] ?? CHUNK_BADGE.prose;
  return (
    <span
      className="text-xs font-mono font-semibold px-2 py-0.5 rounded-full flex-shrink-0"
      style={{ color: badge.color, background: badge.color + '18' }}
    >
      {badge.label}
    </span>
  );
}

// ── Individual chunk row ───────────────────────────────────────────────────────
function ChunkRow({ chunk }) {
  const isTarget = chunk.is_target;

  return (
    <div
      className={`rounded-xl px-3 py-3 transition-colors ${
        isTarget
          ? 'bg-blue-50 border-l-4 border-blue-500'
          : 'bg-gray-50 border border-gray-100'
      }`}
    >
      {/* Meta row */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        {isTarget && (
          <span className="text-xs font-semibold text-blue-600 bg-blue-100 px-2 py-0.5 rounded-full">
            → source
          </span>
        )}
        <ChunkBadge type={chunk.chunk_type} />
        {chunk.page_numbers?.length > 0 && (
          <span className="text-xs text-gray-400">
            p.{chunk.page_numbers.join(', ')}
          </span>
        )}
        <span className="text-xs text-gray-300 ml-auto">
          #{chunk.chunk_index}
        </span>
      </div>

      {/* Content */}
      {chunk.chunk_type === 'code' ? (
        <SyntaxHighlighter
          language="java"
          style={oneDark}
          customStyle={{
            margin: 0,
            borderRadius: '8px',
            fontSize: '12px',
            padding: '12px',
          }}
        >
          {chunk.chunk_text}
        </SyntaxHighlighter>
      ) : (
        <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">
          {chunk.chunk_text}
        </p>
      )}
    </div>
  );
}

// ── Loading skeleton ───────────────────────────────────────────────────────────
function SkeletonPanel() {
  return (
    <div className="p-4 space-y-3 animate-pulse">
      {[1, 2, 3, 4, 5].map(i => (
        <div key={i} className={`rounded-xl p-3 ${i === 3 ? 'bg-blue-50' : 'bg-gray-50'}`}>
          <div className="flex gap-2 mb-2">
            <div className="h-4 w-16 bg-gray-200 rounded-full" />
            <div className="h-4 w-10 bg-gray-200 rounded-full" />
          </div>
          <div className="space-y-1.5">
            <div className="h-3 w-full bg-gray-200 rounded" />
            <div className="h-3 w-4/5 bg-gray-200 rounded" />
            {i === 3 && <div className="h-3 w-3/5 bg-gray-200 rounded" />}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Main panel ─────────────────────────────────────────────────────────────────
export default function ChunkPreviewPanel() {
  const { isOpen, preview, closePreview } = useChunkPreview();
  const [chunks, setChunks]   = useState([]);
  const [title,  setTitle]    = useState('');
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  // Fetch chunks whenever the preview target changes
  useEffect(() => {
    if (!preview) return;

    // Graceful fallback — old messages don't have chunk_index
    if (preview.chunk_index == null) {
      setChunks([]);
      setError('no_index');
      return;
    }

    setLoading(true);
    setError(null);
    setChunks([]);

    chunkPreviewAPI
      .getChunks(preview.document_id, preview.chunk_index, 2)
      .then(res => {
        setChunks(res.data.chunks ?? []);
        setTitle(res.data.title ?? preview.title ?? '');
      })
      .catch(err => {
        console.error('Chunk preview failed:', err);
        setError('fetch_failed');
      })
      .finally(() => setLoading(false));
  }, [preview]);

  // Escape key closes panel
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') closePreview(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [closePreview]);

  return (
    <>
      {/* Backdrop — only visible when open */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          style={{ background: 'rgba(0,0,0,0.25)' }}
          onClick={closePreview}
        />
      )}

      {/* Slide-in panel */}
      <div
        className="fixed top-0 right-0 h-full bg-white shadow-2xl z-50 flex flex-col"
        style={{
          width: '420px',
          transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 0.25s ease-in-out',
        }}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-4 py-3 border-b border-gray-100 flex-shrink-0">
          <div>
            <p className="text-sm font-semibold text-gray-800 truncate">
              📄 {title || preview?.title || 'Document'}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">
              Chunk context · {chunks.length} chunk{chunks.length !== 1 ? 's' : ''}
            </p>
          </div>
          <button
            onClick={closePreview}
            className="text-gray-400 hover:text-gray-600 text-lg leading-none ml-4 flex-shrink-0"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto">

          {loading && <SkeletonPanel />}

          {/* No chunk_index — old message fallback */}
          {!loading && error === 'no_index' && (
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <p className="text-3xl mb-3">📋</p>
              <p className="text-sm font-medium text-gray-600">Context unavailable</p>
              <p className="text-xs text-gray-400 mt-1">
                This source was saved before chunk preview was supported.
                Send a new message to get full context.
              </p>
            </div>
          )}

          {/* Fetch failed */}
          {!loading && error === 'fetch_failed' && (
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <p className="text-3xl mb-3">⚠️</p>
              <p className="text-sm font-medium text-gray-600">Failed to load chunks</p>
              <p className="text-xs text-gray-400 mt-1">
                Check that your backend is running and the document is still indexed.
              </p>
            </div>
          )}

          {/* Chunks */}
          {!loading && !error && chunks.length > 0 && (
            <div className="p-4 space-y-3">
              {chunks.map((chunk) => (
                <ChunkRow key={chunk.chunk_index} chunk={chunk} />
              ))}
            </div>
          )}

        </div>

        {/* Footer */}
        {!loading && !error && chunks.length > 0 && (
          <div className="px-4 py-2 border-t border-gray-100 flex-shrink-0">
            <p className="text-xs text-gray-400">
              Showing ±2 chunks around the source · ESC to close
            </p>
          </div>
        )}
      </div>
    </>
  );
}