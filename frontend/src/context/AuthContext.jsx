import { createContext, useState, useEffect } from 'react';
import { authAPI } from '../services/api';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const savedToken = localStorage.getItem('token');
      if (savedToken) {
        try {
          const response = await authAPI.getMe();
          setUser(response.data);
          setToken(savedToken);
        } catch (error) {
          localStorage.removeItem('token');
          localStorage.removeItem('refresh_token');
          setToken(null);
          setUser(null);
        }
      }
      setLoading(false);
    };
    initAuth();
  }, []);

  const login = async (email, password) => {
    const response = await authAPI.login(email, password);
    const { access_token, refresh_token } = response.data;

    localStorage.setItem('token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    setToken(access_token);

    const userResponse = await authAPI.getMe();
    setUser(userResponse.data);
    return userResponse.data;
  };

  const register = async (email, username, password) => {
    const response = await authAPI.register(email, username, password);
    return response.data;
  };

  const logout = async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      // Continue logout even if API fails
    }
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setUser(null);
  };

  const value = {
    user,
    token,
    loading,
    login,
    register,
    logout,
    isLoggedIn: !!token,
  };

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