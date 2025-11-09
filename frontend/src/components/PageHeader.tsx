import React from 'react';
import { Link } from 'react-router-dom';
import ThemeToggle from './ThemeToggle';

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
    <header className="bg-white dark:bg-gray-800 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="py-6">
          <div className="flex items-center justify-between">
            {/* Left side: Back button + Title */}
            <div className="flex items-center gap-4">
              <Link
                to="/"
                className="inline-flex items-center justify-center w-10 h-10 bg-gray-600 dark:bg-gray-700 text-white rounded-md hover:bg-gray-700 dark:hover:bg-gray-600 transition-colors duration-200"
                title="Back to Home"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </Link>

              <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100">{title}</h1>
                {badge && (
                  <span className={`text-sm px-3 py-1 rounded-full font-medium self-start whitespace-nowrap ${getBadgeColor(badge.color)}`}>
                    {badge.text}
                  </span>
                )}
              </div>
            </div>

            {/* Right side: Theme toggle + Optional children */}
            <div className="flex items-center gap-3">
              <ThemeToggle />
              {children && <div>{children}</div>}
            </div>
          </div>

          {/* Subtitle */}
          {subtitle && (
            <p className="text-gray-600 dark:text-gray-400 mt-2 ml-14">{subtitle}</p>
          )}
        </div>
      </div>
    </header>
  );
};

export default PageHeader;
