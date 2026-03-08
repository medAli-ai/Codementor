import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/useAuth';
import { useSearch } from './context/useSearch';
import Login from './pages/Login';
import Register from './pages/Register';
import Chat from './pages/Chat';
import DocumentLibrary from './pages/DocumentLibrary';
import ProtectedRoute from './components/ProtectedRoute';
import ChunkPreviewPanel from './components/ChunkPreviewPanel';
import SearchModal from './components/SearchModal';

// Cmd+K / Ctrl+K listener — lives here so it's registered once for the whole app
function GlobalSearchShortcut() {
  const { openSearch } = useSearch();

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        openSearch();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [openSearch]);

  return null; // purely behavioural, renders nothing
}

function App() {
  const { isLoggedIn } = useAuth();

  return (
    <BrowserRouter>
      {/* SearchModal needs BrowserRouter (useNavigate) but sits outside Routes */}
      <GlobalSearchShortcut />
      <SearchModal />
      <ChunkPreviewPanel />

      <Routes>
        <Route
          path="/login"
          element={isLoggedIn ? <Navigate to="/chat" /> : <Login />}
        />
        <Route
          path="/register"
          element={isLoggedIn ? <Navigate to="/chat" /> : <Register />}
        />
        <Route
          path="/chat/:conversationId?"
          element={
            <ProtectedRoute>
              <Chat />
            </ProtectedRoute>
          }
        />
        <Route
          path="/library"
          element={
            <ProtectedRoute>
              <DocumentLibrary />
            </ProtectedRoute>
          }
        />
        <Route
          path="*"
          element={<Navigate to={isLoggedIn ? "/chat" : "/login"} />}
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;