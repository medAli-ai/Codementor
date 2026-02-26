import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/useAuth';
import Login from './pages/Login';
import Register from './pages/Register';
import Chat from './pages/Chat';
import DocumentLibrary from './pages/DocumentLibrary';
import ProtectedRoute from './components/ProtectedRoute';

function App() {
  const { isLoggedIn } = useAuth();

  return (
    <BrowserRouter>
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
        {/* NEW: Library page — same ProtectedRoute children pattern */}
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