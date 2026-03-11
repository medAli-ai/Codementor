import { useState, useCallback } from 'react';
import { ChunkPreviewContext } from './ChunkPreviewContext.js';

export function ChunkPreviewProvider({ children }) {
  const [isOpen,  setIsOpen]  = useState(false);
  const [preview, setPreview] = useState(null);

  const openPreview = useCallback((data) => {
    setPreview(data);
    setIsOpen(true);
  }, []);

  const closePreview = useCallback(() => {
    setIsOpen(false);
    setPreview(null);
  }, []);

  return (
    <ChunkPreviewContext.Provider value={{ isOpen, preview, openPreview, closePreview }}>
      {children}
    </ChunkPreviewContext.Provider>
  );
}