import { createContext, useState, useCallback } from 'react';

export const ChunkPreviewContext = createContext(null);

export function ChunkPreviewProvider({ children }) {
  const [isOpen,  setIsOpen]  = useState(false);
  const [preview, setPreview] = useState(null);
  // preview shape: { document_id, chunk_index, title, chunk_type }

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