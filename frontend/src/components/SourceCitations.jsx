// ============================================================
// SourceCitations.jsx
// ============================================================
// Renders below assistant messages in MessageBubble when
// rag_used=true. Collapsible to avoid cluttering the chat.
// Color scheme matches existing: blue-600, gray-xxx.
// ============================================================

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

// Relevance thresholds → color + label
const scoreStyle = (score) => {
  if (score >= 0.85) return { color: '#16a34a', label: 'High' };   // green-600
  if (score >= 0.70) return { color: '#d97706', label: 'Good' };   // amber-600
  return               { color: '#dc2626', label: 'Low' };          // red-600
};

function SourceCitations({ sources = [], ragUsed = false }) {
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();

  // No RAG used or no sources → show subtle "general knowledge" tag
  if (!ragUsed || !sources.length) {
    return (
      <div className="mt-2">
        <span className="text-xs text-gray-400">
          🌐 General knowledge
        </span>
      </div>
    );
  }

  return (
    <div className="mt-3 border-t border-gray-100 pt-2">
      {/* Toggle */}
      <button
        onClick={() => setExpanded(v => !v)}
        className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 font-medium transition-colors"
      >
        📚 {sources.length} source{sources.length > 1 ? 's' : ''} from your library
        <span className="text-gray-400">{expanded ? '▲' : '▼'}</span>
      </button>

      {/* Source list */}
      {expanded && (
        <div className="mt-2 space-y-1">
          {sources.map((source, index) => {
            const style = scoreStyle(source.score);
            return (
              <div
                key={source.document_id ?? index}
                className="flex items-center justify-between rounded-lg bg-gray-50 border border-gray-200 px-3 py-2"
              >
                {/* Document name */}
                <div className="flex items-center gap-1.5 truncate">
  <button
    onClick={() => navigate(`/library?highlight=${source.document_id}`)}
    className="text-xs text-gray-700 hover:text-blue-600 truncate text-left font-medium"
  >
    📄 {source.title}
  </button>
  {source.page_numbers?.length > 0 && (
    <span className="text-xs text-gray-400 flex-shrink-0">
      p.{source.page_numbers.join(', ')}
    </span>
  )}
</div>

                {/* Relevance badge */}
                <span
                  className="text-xs font-semibold ml-3 flex-shrink-0 px-2 py-0.5 rounded-full"
                  style={{
                    color: style.color,
                    background: style.color + '18', // ~10% opacity tint
                  }}
                >
                  {style.label} ({Math.round(source.score * 100)}%)
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default SourceCitations;