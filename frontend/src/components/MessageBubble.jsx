import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

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
        {/* Role Label */}
        <p className={`text-xs font-semibold mb-2 ${isUser ? 'text-blue-200' : 'text-gray-400'}`}>
  {isUser ? '👤 You' : '🤖 CodeMentor'}
  {message.isStreaming && (
    <span className="ml-2 inline-block w-2 h-2 bg-blue-400 rounded-full animate-bounce" />
  )}
</p>

        {/* Content */}
        {isUser ? (
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkMath]}
            rehypePlugins={[rehypeKatex]}
            components={{
              code({ node, inline, className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || '');
                const language = match ? match[1] : 'text';

                return !inline ? (
                  <SyntaxHighlighter
                    style={oneDark}
                    language={language}
                    PreTag="div"
                    {...props}
                  >
                    {String(children).replace(/\n$/, '')}
                  </SyntaxHighlighter>
                ) : (
                  <code
                    style={{
                      background: '#f3f4f6',
                      color: '#db2777',
                      padding: '2px 4px',
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      fontFamily: 'monospace',
                    }}
                  >
                    {children}
                  </code>
                );
              },
              h1: ({ children }) => (
                <h1 style={{ fontSize: '1.1rem', fontWeight: 'bold', marginTop: '12px', marginBottom: '4px' }}>
                  {children}
                </h1>
              ),
              h2: ({ children }) => (
                <h2 style={{ fontSize: '1rem', fontWeight: 'bold', marginTop: '10px', marginBottom: '4px' }}>
                  {children}
                </h2>
              ),
              h3: ({ children }) => (
                <h3 style={{ fontSize: '0.9rem', fontWeight: 'bold', marginTop: '8px', marginBottom: '4px', color: '#374151' }}>
                  {children}
                </h3>
              ),
              p: ({ children }) => (
                <div style={{ marginBottom: '8px', lineHeight: '1.6' }}>{children}</div>
              ),
              ul: ({ children }) => (
                <ul style={{ listStyleType: 'disc', paddingLeft: '20px', marginBottom: '8px' }}>
                  {children}
                </ul>
              ),
              ol: ({ children }) => (
                <ol style={{ listStyleType: 'decimal', paddingLeft: '20px', marginBottom: '8px' }}>
                  {children}
                </ol>
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
                  fontStyle: 'italic'
                }}>
                  {children}
                </blockquote>
              ),
            }}
          >
            {message.content}
          </ReactMarkdown>
        )}
      </div>
    </div>
  );
}

export default MessageBubble;