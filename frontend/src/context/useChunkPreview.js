import { useContext } from 'react';
import { ChunkPreviewContext } from './ChunkPreviewContext';

export function useChunkPreview() {
  const ctx = useContext(ChunkPreviewContext);
  if (!ctx) throw new Error('useChunkPreview must be used inside <ChunkPreviewProvider>');
  return ctx;
}
