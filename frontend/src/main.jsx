import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import { SearchProvider } from './context/SearchContext.jsx';
import { ChunkPreviewProvider } from './context/ChunkPreviewContext.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <SearchProvider>
      <ChunkPreviewProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ChunkPreviewProvider>
    </SearchProvider>
  </StrictMode>,
)