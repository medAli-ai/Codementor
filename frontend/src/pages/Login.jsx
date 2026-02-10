import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

function Login() {
  // Form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  
  // UI state
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  
  // Hooks
  const { login } = useAuth();        // Get login function from context
  const navigate = useNavigate();     // For redirecting after login

  const handleSubmit = async (e) => {
    e.preventDefault();  // Prevent page refresh on form submit
    
    // Reset error
    setError('');
    
    // Basic validation
    if (!email || !password) {
      setError('Please fill in all fields');
      return;
    }
    
    setLoading(true);
    
    try {
      // Call login from AuthContext
      await login(email, password);
      
      // Redirect to chat on success
      navigate('/chat');
      
    } catch (err) {
      // Show error message
      const message = err.response?.data?.detail || 'Login failed. Please try again.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
        
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-blue-600">🎓 CodeMentor</h1>
          <p className="text-gray-500 mt-2">Sign in to your account</p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          
          {/* Email Field */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading}
            />
          </div>

          {/* Password Field */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading}
            />
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>

        </form>

        {/* Register Link */}
        <p className="text-center text-gray-500 mt-6">
          No account?{' '}
          <Link to="/register" className="text-blue-600 hover:underline font-medium">
            Register here
          </Link>
        </p>

      </div>
    </div>
  );
}

export default Login;