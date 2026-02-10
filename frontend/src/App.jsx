import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Register from './pages/Register';
import ProtectedRoute from './components/ProtectedRoute';

function App() {
  const { isLoggedIn } = useAuth();
  
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route 
          path="/login" 
          element={isLoggedIn ? <Navigate to="/chat" /> : <Login />} 
        />
        <Route 
          path="/register" 
          element={isLoggedIn ? <Navigate to="/chat" /> : <Register />} 
        />
        
        {/* Protected routes */}
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <div className="min-h-screen bg-gray-100 flex items-center justify-center">
                <h1 className="text-2xl font-bold text-gray-700">
                  Chat Page Coming Soon! 🚀
                </h1>
              </div>
            </ProtectedRoute>
          }
        />
        
        {/* Default redirect */}
        <Route 
          path="*" 
          element={<Navigate to={isLoggedIn ? "/chat" : "/login"} />} 
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;