import React from 'react';
import ThemeToggle from './ThemeToggle';
import { useSidebar } from '../contexts/SidebarContext';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  badge?: {
    text: string;
    color?: 'blue' | 'green' | 'gray';
  };
  children?: React.ReactNode;
}

const PageHeader: React.FC<PageHeaderProps> = ({ title, subtitle, badge, children }) => {
  const { toggleSidebar, isSidebarOpen } = useSidebar();

  const getBadgeColor = (color: 'blue' | 'green' | 'gray' = 'gray') => {
    switch (color) {
      case 'blue':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'green':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'gray':
      default:
        return 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-300';
    }
  };

  return (
    <header className="mx-2 mt-2 bg-gray-50 dark:bg-gray-800 shadow-sm rounded-lg relative">
      <div className="py-6 relative">
        {/* Hamburger Menu Button - absolutely positioned, doesn't affect layout flow */}
        <button
          onClick={toggleSidebar}
          className="absolute left-4 top-1/2 -translate-y-1/2 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors z-10"
          aria-label="Toggle sidebar"
          title="Toggle sidebar"
        >
          <svg className="w-6 h-6 text-gray-700 dark:text-gray-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        {/* Shifting wrapper - matches main content shift */}
        <div className={`transition-all duration-300 ${isSidebarOpen ? 'ml-60' : 'ml-0'}`}>
          {/* Center content area */}
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex items-center justify-between">
                {/* Left side: Title + Subtitle */}
                <div className="flex flex-col gap-2">
                  <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                    <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100">{title}</h1>
                    {badge && (
                      <span className={`text-sm px-3 py-1 rounded-full font-medium self-start sm:self-center whitespace-nowrap ${getBadgeColor(badge.color)}`}>
                        {badge.text}
                      </span>
                    )}
                  </div>

                  {/* Subtitle - aligned with title */}
                  {subtitle && (
                    <p className="text-gray-600 dark:text-gray-400">{subtitle}</p>
                  )}
                </div>

                {/* Right side: Theme toggle + Optional children */}
                <div className="flex items-center gap-3">
                  <ThemeToggle />
                  {children && <div>{children}</div>}
                </div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default PageHeader;
