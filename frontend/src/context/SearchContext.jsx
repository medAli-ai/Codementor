import { useState, useCallback } from 'react';
import { SearchContext } from './SearchContext.js';

export function SearchProvider({ children }) {
  const [isOpen, setIsOpen] = useState(false);

  const openSearch  = useCallback(() => setIsOpen(true),  []);
  const closeSearch = useCallback(() => setIsOpen(false), []);

  return (
    <SearchContext.Provider value={{ isOpen, openSearch, closeSearch }}>
      {children}
    </SearchContext.Provider>
  );
}