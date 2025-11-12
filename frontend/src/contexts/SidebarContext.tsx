import React, { createContext, useContext, useState, useEffect } from 'react';

interface SidebarContextType {
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
}

const SidebarContext = createContext<SidebarContextType | undefined>(undefined);

export const SidebarProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Initialize from localStorage, default to open on desktop, closed on mobile
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(() => {
    const saved = localStorage.getItem('sidebarOpen');
    if (saved !== null) {
      return saved === 'true';
    }
    // Default to open on desktop (width >= 1024px), closed on mobile
    return window.innerWidth >= 1024;
  });

  // Save to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('sidebarOpen', String(isSidebarOpen));
  }, [isSidebarOpen]);

  const toggleSidebar = () => {
    setIsSidebarOpen(prev => !prev);
  };

  return (
    <SidebarContext.Provider value={{ isSidebarOpen, toggleSidebar }}>
      {children}
    </SidebarContext.Provider>
  );
};

export const useSidebar = (): SidebarContextType => {
  const context = useContext(SidebarContext);
  if (context === undefined) {
    throw new Error('useSidebar must be used within a SidebarProvider');
  }
  return context;
};
