import { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../services/api';

// Create the context
const AuthContext = createContext(null);

// Provider component - wraps our entire app
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  // Check if user is logged in on app load
  useEffect(() => {
    const initAuth = async () => {
      const savedToken = localStorage.getItem('token');
      
      if (savedToken) {
        try {
          // Verify token is still valid
          const response = await authAPI.getMe();
          setUser(response.data);
          setToken(savedToken);
        } catch (error) {
          // Token invalid/expired - clear everything
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          setToken(null);
          setUser(null);
        }
      }
      
      setLoading(false);
    };
    
    initAuth();
  }, []);

  const login = async (email, password) => {
    // Call login API
    const response = await authAPI.login(email, password);
    const { access_token } = response.data;
    
    // Save token
    localStorage.setItem('token', access_token);
    setToken(access_token);
    
    // Get user info
    const userResponse = await authAPI.getMe();
    setUser(userResponse.data);
    
    return userResponse.data;
  };

  const register = async (email, username, password) => {
    // Call register API
    const response = await authAPI.register(email, username, password);
    return response.data;
  };

  const logout = () => {
    // Clear everything
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
  };

  // Values available to all components
  const value = {
    user,        // Current user object
    token,       // JWT token
    loading,     // Is auth loading?
    login,       // Login function
    register,    // Register function
    logout,      // Logout function
    isLoggedIn: !!token,  // Boolean: is user logged in?
  };

  // Show loading spinner while checking auth
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-gray-500 text-xl">Loading...</div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

// Custom hook - easy way to use auth in any component
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}