import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';

function ProtectedRoute({ children }) {
  const { isLoggedIn } = useAuth();
  
  // If not logged in, redirect to login page
  if (!isLoggedIn) {
    return <Navigate to="/login" replace />;
  }
  
  // If logged in, show the page
  return children;
}

export default ProtectedRoute;