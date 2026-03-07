import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSearch } from '../context/useSearch';
import { searchAPI } from '../services/api';

// ── Chunk type badge — mirrors SourceCitations.jsx ────────────────────────────
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

// ── Score pill ─────────────────────────────────────────────────────────────────
function ScorePill({ score }) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? '#059669' : pct >= 65 ? '#d97706' : '#6b7280';
  return (
    <span
      className="text-xs font-semibold px-2 py-0.5 rounded-full flex-shrink-0"
      style={{ color, background: color + '18' }}
    >
      {pct}%
    </span>
  );
}

// ── Skeleton loader ────────────────────────────────────────────────────────────
function SkeletonResults() {
  return (
    <div className="p-4 space-y-4 animate-pulse">
      {[1, 2].map(g => (
        <div key={g}>
          <div className="h-3 w-32 bg-gray-200 rounded mb-2" />
          {[1, 2, 3].map(r => (
            <div key={r} className="mb-2 rounded-xl border border-gray-100 p-3">
              <div className="flex gap-2 mb-2">
                <div className="h-4 w-16 bg-gray-200 rounded-full" />
                <div className="h-4 w-10 bg-gray-200 rounded-full" />
              </div>
              <div className="h-3 w-full bg-gray-100 rounded mb-1" />
              <div className="h-3 w-3/4 bg-gray-100 rounded" />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

// ── Group results by document ─────────────────────────────────────────────────
function groupByDocument(results) {
  const map = new Map();
  for (const r of results) {
    if (!map.has(r.document_id)) {
      map.set(r.document_id, { title: r.title, document_id: r.document_id, chunks: [] });
    }
    map.get(r.document_id).chunks.push(r);
  }
  return Array.from(map.values());
}

// ── Main modal ─────────────────────────────────────────────────────────────────
export default function SearchModal() {
  const { isOpen, closeSearch } = useSearch();
  const navigate = useNavigate();

  const [query,   setQuery]   = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false); // true once first search fired

  const inputRef    = useRef(null);
  const debounceRef = useRef(null);

  // Auto-focus input when modal opens; reset state when it closes
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery('');
      setResults([]);
      setSearched(false);
    }
  }, [isOpen]);

  // Escape key closes modal
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') closeSearch(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [closeSearch]);

  // Debounced search
  const handleQueryChange = useCallback((e) => {
    const value = e.target.value;
    setQuery(value);

    clearTimeout(debounceRef.current);

    if (!value.trim()) {
      setResults([]);
      setSearched(false);
      setLoading(false);
      return;
    }

    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await searchAPI.search(value.trim());
        setResults(res.data.results ?? []);
      } catch (err) {
        console.error('Search failed:', err);
        setResults([]);
      } finally {
        setLoading(false);
        setSearched(true);
      }
    }, 350);
  }, []);

  const handleResultClick = useCallback((documentId) => {
    navigate(`/library?highlight=${documentId}`);
    closeSearch();
  }, [navigate, closeSearch]);

  if (!isOpen) return null;

  const groups = groupByDocument(results);

  return (
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4"
      style={{ background: 'rgba(0,0,0,0.45)' }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) closeSearch(); }}
    >
      {/* Panel */}
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl flex flex-col overflow-hidden"
           style={{ maxHeight: '70vh' }}>

        {/* Search input row */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100">
          <span className="text-gray-400 text-lg">🔍</span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={handleQueryChange}
            placeholder="Search your documents…"
            className="flex-1 text-sm text-gray-800 placeholder-gray-400 outline-none bg-transparent"
          />
          <div className="flex items-center gap-2 flex-shrink-0">
            <kbd className="hidden sm:inline-flex items-center gap-1 rounded-md border border-gray-200 px-1.5 py-0.5 text-xs text-gray-400">
              ⌘K
            </kbd>
            <button
              onClick={closeSearch}
              className="text-xs text-gray-400 hover:text-gray-600 border border-gray-200 rounded-md px-1.5 py-0.5"
            >
              ESC
            </button>
          </div>
        </div>

        {/* Results area */}
        <div className="overflow-y-auto flex-1">

          {/* Loading skeleton */}
          {loading && <SkeletonResults />}

          {/* Results grouped by doc */}
          {!loading && groups.length > 0 && (
            <div className="p-4 space-y-5">
              {groups.map(group => (
                <div key={group.document_id}>
                  {/* Document header */}
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2 px-1">
                    📄 {group.title}
                  </p>

                  <div className="space-y-2">
                    {group.chunks.map((chunk, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleResultClick(group.document_id)}
                        className="w-full text-left rounded-xl border border-gray-100 hover:border-blue-200 hover:bg-blue-50 px-3 py-2.5 transition-colors"
                      >
                        {/* Meta row */}
                        <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                          <ChunkBadge type={chunk.chunk_type} />
                          {chunk.page_numbers?.length > 0 && (
                            <span className="text-xs text-gray-400">
                              p.{chunk.page_numbers.join(', ')}
                            </span>
                          )}
                          <ScorePill score={chunk.score} />
                        </div>

                        {/* Chunk preview */}
                        <p className="text-xs text-gray-600 leading-relaxed line-clamp-3">
                          {chunk.chunk_text}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Empty — no query */}
          {!loading && !searched && (
            <div className="flex flex-col items-center justify-center py-16 text-center px-4">
              <p className="text-3xl mb-3">🔍</p>
              <p className="text-sm font-medium text-gray-600">Search across your documents</p>
              <p className="text-xs text-gray-400 mt-1">
                Try a concept, keyword, or question from your study material
              </p>
            </div>
          )}

          {/* Empty — searched but no results */}
          {!loading && searched && results.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center px-4">
              <p className="text-3xl mb-3">📭</p>
              <p className="text-sm font-medium text-gray-600">No results for "{query}"</p>
              <p className="text-xs text-gray-400 mt-1">
                Try a different keyword, or check that your documents are fully indexed
              </p>
            </div>
          )}

        </div>

        {/* Footer */}
        {!loading && results.length > 0 && (
          <div className="px-4 py-2 border-t border-gray-100 flex items-center justify-between">
            <p className="text-xs text-gray-400">{results.length} chunk{results.length !== 1 ? 's' : ''} found</p>
            <p className="text-xs text-gray-400">Click a result to open in Library</p>
          </div>
        )}
      </div>
    </div>
  );
}