import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import SourceCitations from './SourceCitations';

function detectLanguage(code) {
  const s = code.trim();
  if (/public\s+class\s|System\.out\.|void\s+main\s*\(|import\s+java\./.test(s)) return 'java';
  if (/def\s+\w+\s*\(|import\s+\w+|print\s*\(|:\s*$/.test(s))                   return 'python';
  if (/const\s|let\s|var\s|=>\s*{|console\.log|require\(/.test(s))              return 'javascript';
  if (/interface\s+\w+|:\s*string|:\s*number|:\s*boolean/.test(s))              return 'typescript';
  if (/#include\s*<|int\s+main\s*\(|std::/.test(s))                             return 'cpp';
  if (/SELECT\s|INSERT\s|UPDATE\s|FROM\s|WHERE\s/i.test(s))                     return 'sql';
  if (/^\s*<\w+|<\/\w+>/.test(s))                                               return 'html';
  if (/^\s*[.#]\w+\s*\{|:\s*\w+\s*;/.test(s))                                  return 'css';
  if (/^(FROM|RUN|CMD|EXPOSE|ENV|COPY)\s/m.test(s))                             return 'docker';
  return 'text';
}

function isSingleLineSnippet(code) {
  const lines = code.trim().split('\n');
  return lines.length === 1 && code.trim().length <= 80;
}

// ─── Extracted code block component ──────────────────────────────────────────
function CodeBlock({ inline, className, children, ...props }) {
  const match = /language-(\w+)/.exec(className || '');
  const codeString = String(children).replace(/\n$/, '');
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(codeString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Inline code — always render as chip
  if (inline) {
    return (
      <code style={{
        background: '#f3f4f6',
        color: '#db2777',
        padding: '2px 6px',
        borderRadius: '4px',
        fontSize: '0.75rem',
        fontFamily: 'monospace',
      }}>
        {children}
      </code>
    );
  }

  // Single-line safety net
  if (isSingleLineSnippet(codeString)) {
    return (
      <code style={{
        display: 'inline-block',
        background: '#f3f4f6',
        color: '#db2777',
        padding: '2px 6px',
        borderRadius: '4px',
        fontSize: '0.75rem',
        fontFamily: 'monospace',
        margin: '2px 0',
      }}>
        {codeString}
      </code>
    );
  }

  // Multi-line block
  const language = match ? match[1] : detectLanguage(codeString);

  return (
    <div style={{ position: 'relative', marginBottom: '12px' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: '#282c34',
        borderRadius: '6px 6px 0 0',
        padding: '6px 12px',
      }}>
        <span style={{
          fontSize: '0.65rem',
          color: '#abb2bf',
          fontFamily: 'monospace',
          background: '#3e4451',
          border: '1px solid #4b5263',
          borderRadius: '999px',
          padding: '2px 8px',
          textTransform: 'lowercase',
          letterSpacing: '0.03em',
        }}>
          {language}
        </span>
        <button
          onClick={handleCopy}
          style={{
            fontSize: '0.7rem',
            color: copied ? '#98c379' : '#abb2bf',
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            fontFamily: 'monospace',
            transition: 'color 0.2s',
          }}
        >
          {copied ? '✓ Copied' : 'Copy'}
        </button>
      </div>
      <SyntaxHighlighter
        style={oneDark}
        language={language}
        PreTag="div"
        customStyle={{ borderRadius: '0 0 6px 6px', marginTop: 0 }}
        {...props}
      >
        {codeString}
      </SyntaxHighlighter>
    </div>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────
function MessageBubble({ message }) {
  const isUser = message.role === 'user';

  return (
    <div style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
      <div className={`
        max-w-3xl rounded-2xl px-4 py-3 text-sm shadow-sm
        ${isUser
          ? 'bg-blue-600 text-white'
          : 'bg-white text-gray-800 border border-gray-100'
        }
        ${message.isLoading ? 'animate-pulse' : ''}
      `}>
        <p className={`text-xs font-semibold mb-2 ${isUser ? 'text-blue-200' : 'text-gray-400'}`}>
          {isUser ? '👤 You' : '🤖 CodeMentor'}
          {message.isStreaming && (
            <span className="ml-2 inline-block w-2 h-2 bg-blue-400 rounded-full animate-bounce" />
          )}
        </p>

        {isUser ? (
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkMath]}
            rehypePlugins={[rehypeKatex]}
            components={{
              code: CodeBlock,
              h1: ({ children }) => (
                <h1 style={{ fontSize: '1.1rem', fontWeight: 'bold', marginTop: '12px', marginBottom: '4px' }}>{children}</h1>
              ),
              h2: ({ children }) => (
                <h2 style={{ fontSize: '1rem', fontWeight: 'bold', marginTop: '10px', marginBottom: '4px' }}>{children}</h2>
              ),
              h3: ({ children }) => (
                <h3 style={{ fontSize: '0.9rem', fontWeight: 'bold', marginTop: '8px', marginBottom: '4px', color: '#374151' }}>{children}</h3>
              ),
              p: ({ children }) => (
                <div style={{ marginBottom: '8px', lineHeight: '1.6' }}>{children}</div>
              ),
              ul: ({ children }) => (
                <ul style={{ listStyleType: 'disc', paddingLeft: '20px', marginBottom: '8px' }}>{children}</ul>
              ),
              ol: ({ children }) => (
                <ol style={{ listStyleType: 'decimal', paddingLeft: '20px', marginBottom: '8px' }}>{children}</ol>
              ),
              li: ({ children }) => (
                <li style={{ marginBottom: '2px', fontSize: '0.875rem' }}>{children}</li>
              ),
              strong: ({ children }) => (
                <strong style={{ fontWeight: '600', color: '#111827' }}>{children}</strong>
              ),
              blockquote: ({ children }) => (
                <blockquote style={{
                  borderLeft: '3px solid #d1d5db',
                  paddingLeft: '12px',
                  color: '#6b7280',
                  margin: '8px 0',
                  fontStyle: 'italic',
                }}>
                  {children}
                </blockquote>
              ),
            }}
          >
            {message.content}
          </ReactMarkdown>
        )}

        {!isUser && !message.isStreaming && (
          <SourceCitations sources={message.sources || []} ragUsed={message.rag_used || false} />
        )}
      </div>
    </div>
  );
}

export default MessageBubble;