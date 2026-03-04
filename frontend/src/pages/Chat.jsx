import { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { conversationsAPI, streamMessage } from '../services/api';
import MessageBubble from '../components/MessageBubble';


function Chat() {
  // ============ State ============
  const [conversations, setConversations] = useState([]);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sidebarLoading, setSidebarLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [editingTitle, setEditingTitle] = useState('');
  // NEW: RAG toggle — lets users ask general questions without searching docs
  const [useRag, setUseRag] = useState(true);

  const messagesEndRef = useRef(null);
  const justStreamedRef = useRef(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { conversationId: urlConversationId } = useParams();

  // ============ Effects ============

  // 1. Load sidebar conversations when user changes
  useEffect(() => {
    loadConversations();
  }, [user]);

  // 2. When URL conversation ID changes, load that conversation
  useEffect(() => {
    if (!urlConversationId) {
      setCurrentConversation(null);
      setMessages([]);
      return;
    }
    if (conversations.length === 0) return;
    const conv = conversations.find(c => c.id === parseInt(urlConversationId));
    if (!conv) return;

    // Don't re-fetch messages if we just finished streaming (sources would be lost)
    if (justStreamedRef.current) {
      setCurrentConversation(conv);
      return;
    }

    setCurrentConversation(conv);
    conversationsAPI.get(conv.id)
      .then(res => setMessages(
    res.data.messages.map(m => ({
      ...m,
      sources:  m.sources  ?? [],
      rag_used: m.rag_used ?? false,
    }))
  ))
      .catch(err => console.error('Failed to load conversation:', err));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlConversationId, conversations]);

  // 3. Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ============ Conversation Functions ============

  const loadConversations = async () => {
    try {
      setSidebarLoading(true);
      const response = await conversationsAPI.list();
      setConversations(response.data);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    } finally {
      setSidebarLoading(false);
    }
  };

  // Only navigate — the URL effect handles loading
  const selectConversation = (conversation) => {
    navigate(`/chat/${conversation.id}`);
  };

  const startNewConversation = () => {
    navigate('/chat');
  };

  const startRename = (conversation) => {
    setEditingId(conversation.id);
    setEditingTitle(conversation.title);
  };

  const cancelRename = () => {
    setEditingId(null);
    setEditingTitle('');
  };

  const saveRename = async (conversationId) => {
    if (!editingTitle.trim()) return cancelRename();
    try {
      await conversationsAPI.update(conversationId, editingTitle.trim());
      setConversations(prev => prev.map(c =>
        c.id === conversationId ? { ...c, title: editingTitle.trim() } : c
      ));
      if (currentConversation?.id === conversationId) {
        setCurrentConversation(prev => ({ ...prev, title: editingTitle.trim() }));
      }
    } catch (error) {
      console.error('Failed to rename:', error);
    } finally {
      cancelRename();
    }
  };

  const deleteConversation = async (e, conversationId) => {
    e.stopPropagation();
    try {
      await conversationsAPI.delete(conversationId);
      setConversations(prev => prev.filter(c => c.id !== conversationId));
      if (currentConversation?.id === conversationId) {
        setCurrentConversation(null);
        setMessages([]);
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  // ============ Chat Functions ============

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    setLoading(true);

    const tempUserMsg = {
      id: Date.now(),
      role: 'user',
      content: userMessage,
    };

    const tempAssistantId = Date.now() + 1;
    const tempAssistantMsg = {
      id: tempAssistantId,
      role: 'assistant',
      content: '',
      isStreaming: true,
      sources: [],
      rag_used: false,
    };

    setMessages(prev => [...prev, tempUserMsg, tempAssistantMsg]);

    try {
      let accumulatedContent = '';

      await streamMessage(
        userMessage,
        currentConversation?.id || null,
        0.7,
        useRag,

        // onChunk
        (chunk) => {
          accumulatedContent += chunk;
          setMessages(prev => prev.map(msg =>
            msg.id === tempAssistantId
              ? { ...msg, content: accumulatedContent, isStreaming: true }
              : msg
          ));
        },

        // onDone
        async (conversationId, messageId, sources, ragUsed) => {
          setMessages(prev => prev.map(msg =>
            msg.id === tempAssistantId
              ? {
                  ...msg,
                  isStreaming: false,
                  sources: sources,
                  rag_used: ragUsed,
                }
              : msg
          ));

          // If new conversation was created, update sidebar
          if (!currentConversation) {
            // Block the URL effect from re-fetching messages for the next 3 seconds
            justStreamedRef.current = true;
            setTimeout(() => { justStreamedRef.current = false; }, 3000);

            const newConv = await conversationsAPI.get(conversationId);
            setCurrentConversation(newConv.data);
            navigate(`/chat/${conversationId}`);
            loadConversations();
          }
        }
      );

    } catch (error) {
      console.error('Failed to send message:', error);
      setMessages(prev => prev.filter(msg => msg.id !== tempAssistantId));
      setMessages(prev => [...prev, {
        id: Date.now(),
        role: 'assistant',
        content: '❌ Failed to get response. Please try again.',
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ============ Render ============
  return (
    <div className="flex h-screen bg-gray-100">

      {/* ===== SIDEBAR ===== */}
      <div className="w-64 bg-gray-900 text-white flex flex-col">

        {/* Logo */}
        <div className="p-4 border-b border-gray-700">
          <h1 className="text-xl font-bold text-blue-400">🎓 CodeMentor</h1>
          <p className="text-gray-400 text-sm">AI Coding Tutor</p>
        </div>

        {/* New Chat Button */}
        <div className="p-3 space-y-2">
          <button
            onClick={startNewConversation}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2 px-4 text-sm font-medium transition-colors"
          >
            + New Chat
          </button>

          {/* Library navigation */}
          <button
            onClick={() => navigate('/library')}
            className="w-full bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg py-2 px-4 text-sm font-medium transition-colors text-left"
          >
            📚 My Library
          </button>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto px-3 space-y-1">
          {sidebarLoading ? (
            <p className="text-gray-400 text-sm text-center py-4">Loading...</p>
          ) : conversations.length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-4">
              No conversations yet
            </p>
          ) : (
            conversations.map(conversation => (
              <div
                key={`conv-${conversation.id}`}
                onClick={() => editingId !== conversation.id && selectConversation(conversation)}
                className={`
                  group flex items-center justify-between
                  rounded-lg px-3 py-2 cursor-pointer text-sm transition-colors
                  ${currentConversation?.id === conversation.id
                    ? 'bg-gray-700 text-white'
                    : 'text-gray-300 hover:bg-gray-800'
                  }
                `}
              >
                {editingId === conversation.id ? (
                  <div className="flex items-center gap-1 flex-1">
                    <input
                      autoFocus
                      value={editingTitle}
                      onChange={(e) => setEditingTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveRename(conversation.id);
                        if (e.key === 'Escape') cancelRename();
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="bg-gray-600 text-white rounded px-2 py-0.5 text-xs w-full focus:outline-none focus:ring-1 focus:ring-blue-400"
                    />
                    <button
                      onClick={(e) => { e.stopPropagation(); saveRename(conversation.id); }}
                      className="text-green-400 hover:text-green-300 text-xs flex-shrink-0"
                    >✓</button>
                    <button
                      onClick={(e) => { e.stopPropagation(); cancelRename(); }}
                      className="text-red-400 hover:text-red-300 text-xs flex-shrink-0"
                    >✗</button>
                  </div>
                ) : (
                  <>
                    <span
                      className="truncate flex-1"
                      onDoubleClick={(e) => { e.stopPropagation(); startRename(conversation); }}
                      title="Double-click to rename"
                    >
                      💬 {conversation.title}
                    </span>
                    <button
                      onClick={(e) => deleteConversation(e, conversation.id)}
                      className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-400 ml-2 transition-opacity text-xs flex-shrink-0"
                    >🗑️</button>
                  </>
                )}
              </div>
            ))
          )}
        </div>

        {/* User Info + Logout */}
        <div className="p-4 border-t border-gray-700">
          <p className="text-gray-400 text-sm truncate mb-2">
            👤 {user?.username}
          </p>
          <button
            onClick={logout}
            className="w-full text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg py-2 px-4 text-sm transition-colors text-left"
          >
            🚪 Logout
          </button>
        </div>

      </div>

      {/* ===== MAIN CHAT AREA ===== */}
      <div className="flex-1 flex flex-col">

        {/* Chat Header */}
        <div className="bg-white border-b px-6 py-4 shadow-sm">
          <h2 className="font-semibold text-gray-800">
            {currentConversation ? currentConversation.title : 'New Conversation'}
          </h2>
          <p className="text-gray-400 text-sm">
            {currentConversation
              ? `${messages.length} messages`
              : 'Start typing to begin'
            }
          </p>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">

          {/* Welcome Screen */}
          {!currentConversation && messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="text-6xl mb-4">🎓</div>
              <h2 className="text-2xl font-bold text-gray-700 mb-2">
                Welcome, {user?.username}!
              </h2>
              <p className="text-gray-500 max-w-md mb-6">
                Ask me anything about coding. I can help with Python,
                JavaScript, algorithms, debugging, and more!
              </p>
              <div className="grid grid-cols-2 gap-3 max-w-lg">
                {[
                  "Explain Python classes",
                  "How does async/await work?",
                  "What is Big O notation?",
                  "Debug my JavaScript code",
                ].map(suggestion => (
                  <button
                    key={suggestion}
                    onClick={() => setInput(suggestion)}
                    className="bg-white border border-gray-200 rounded-lg px-4 py-3 text-sm text-gray-600 hover:border-blue-400 hover:text-blue-600 transition-colors text-left shadow-sm"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.map(message => (
            <MessageBubble key={`msg-${message.id}`} message={message} />
          ))}

          <div ref={messagesEndRef} />
        </div>

        {/* Message Input */}
        <div className="bg-white border-t p-4">

          {/* RAG toggle */}
          <div className="flex justify-end max-w-4xl mx-auto mb-2">
            <button
              onClick={() => setUseRag(v => !v)}
              className={`
                text-xs px-3 py-1 rounded-full border transition-colors
                ${useRag
                  ? 'bg-blue-50 border-blue-200 text-blue-600'
                  : 'bg-gray-50 border-gray-200 text-gray-400'
                }
              `}
            >
              {useRag ? '📚 Using your library' : '🌐 General knowledge only'}
            </button>
          </div>

          <div className="flex gap-3 max-w-4xl mx-auto">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask CodeMentor anything... (Enter to send, Shift+Enter for new line)"
              disabled={loading}
              rows={2}
              className="flex-1 border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 resize-none"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl px-6 font-medium transition-colors"
            >
              {loading ? '⏳' : '➤'}
            </button>
          </div>
          <p className="text-center text-gray-400 text-xs mt-2">
            Powered by Ollama
          </p>
        </div>

      </div>
    </div>
  );
}

export default Chat;