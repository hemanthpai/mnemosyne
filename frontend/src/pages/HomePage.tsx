import React from "react";
import { Link } from "react-router-dom";
import QueueStatus from "../components/QueueStatus";
import ThemeToggle from "../components/ThemeToggle";
import { useSidebar } from "../contexts/SidebarContext";

const HomePage: React.FC = () => {
    const { toggleSidebar, isSidebarOpen } = useSidebar();

    return (
        <div className="min-h-screen bg-gray-100 dark:bg-gray-900">
            {/* Header - stays in place */}
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
                                <div className="flex justify-between items-center">
                                    <div className="flex flex-col gap-2">
                                        <div className="flex items-center gap-4">
                                            {/* Title */}
                                            <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
                                                Mnemosyne
                                            </h1>
                                            <span className="text-sm text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded-full">
                                                Memory Service
                                            </span>
                                        </div>
                                        {/* Subtitle */}
                                        <p className="text-gray-600 dark:text-gray-400">
                                            Persist and retrieve memories to help AI models remember important items from past interactions with users.
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <ThemeToggle />
                                    </div>
                                </div>
                        </div>
                    </div>
                </div>
            </header>

            {/* Main Content - shifts when sidebar opens */}
            <div className={`transition-all duration-300 ${isSidebarOpen ? 'ml-60' : 'ml-0'}`}>
                <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
                {/* Queue Status */}
                <div className="mb-8">
                    <QueueStatus />
                </div>

                {/* Feature Cards */}
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
                    {/* Import Card */}
                    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 h-full">
                        <div className="p-8 h-full flex flex-col gap-4">
                            <div className="flex items-center gap-3">
                                <div className="bg-orange-100 dark:bg-orange-900 p-3 rounded-lg">
                                    <svg
                                        className="w-6 h-6 text-orange-600 dark:text-orange-400"
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                                        />
                                    </svg>
                                </div>
                                <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                                    Import
                                </h3>
                            </div>
                            <p className="text-gray-600 dark:text-gray-300 text-sm text-left flex-grow leading-relaxed">
                                Import conversation history from Open WebUI and extract atomic notes automatically.
                            </p>
                            <Link
                                to="/import"
                                className="inline-flex items-center px-4 py-2 bg-orange-600 text-white font-medium rounded-lg hover:bg-orange-700 transition-colors duration-200 text-sm"
                            >
                                Import Data
                                <svg
                                    className="ml-2 w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M13 7l5 5m0 0l-5 5m5-5H6"
                                    />
                                </svg>
                            </Link>
                        </div>
                    </div>

                    {/* Notes Card */}
                    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 h-full">
                        <div className="p-8 h-full flex flex-col gap-4">
                            <div className="flex items-center gap-3">
                                <div className="bg-indigo-100 dark:bg-indigo-900 p-3 rounded-lg">
                                    <svg
                                        className="w-6 h-6 text-indigo-600 dark:text-indigo-400"
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
                                        />
                                    </svg>
                                </div>
                                <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                                    Atomic Notes
                                </h3>
                            </div>
                            <p className="text-gray-600 dark:text-gray-300 text-sm text-left flex-grow leading-relaxed">
                                View and manage extracted atomic facts from your conversations. Browse knowledge graph.
                            </p>
                            <Link
                                to="/notes"
                                className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 transition-colors duration-200 text-sm"
                            >
                                View Notes
                                <svg
                                    className="ml-2 w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M13 7l5 5m0 0l-5 5m5-5H6"
                                    />
                                </svg>
                            </Link>
                        </div>
                    </div>

                    {/* Knowledge Graph Card */}
                    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 h-full">
                        <div className="p-8 h-full flex flex-col gap-4">
                            <div className="flex items-center gap-3">
                                <div className="bg-cyan-100 dark:bg-cyan-900 p-3 rounded-lg">
                                    <svg
                                        className="w-6 h-6 text-cyan-600 dark:text-cyan-400"
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"
                                        />
                                    </svg>
                                </div>
                                <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                                    Knowledge Graph
                                </h3>
                            </div>
                            <p className="text-gray-600 dark:text-gray-300 text-sm text-left flex-grow leading-relaxed">
                                Interactive visualization of your knowledge graph showing atomic notes and their relationships.
                            </p>
                            <Link
                                to="/graph"
                                className="inline-flex items-center px-4 py-2 bg-cyan-600 text-white font-medium rounded-lg hover:bg-cyan-700 transition-colors duration-200 text-sm"
                            >
                                View Graph
                                <svg
                                    className="ml-2 w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M13 7l5 5m0 0l-5 5m5-5H6"
                                    />
                                </svg>
                            </Link>
                        </div>
                    </div>

                    {/* Settings Card */}
                    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 h-full">
                        <div className="p-8 h-full flex flex-col gap-4">
                            <div className="flex items-center gap-3">
                                <div className="bg-green-100 dark:bg-green-900 p-3 rounded-lg">
                                    <svg
                                        className="w-6 h-6 text-green-600 dark:text-green-400"
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                                        />
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                                        />
                                    </svg>
                                </div>
                                <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                                    Settings
                                </h3>
                            </div>
                            <p className="text-gray-600 dark:text-gray-300 text-sm text-left flex-grow leading-relaxed">
                                Configure LLM providers, models, and parameters for both embeddings and text generation.
                            </p>
                            <Link
                                to="/settings"
                                className="inline-flex items-center px-4 py-2 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 transition-colors duration-200 text-sm"
                            >
                                Open Settings
                                <svg
                                    className="ml-2 w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M13 7l5 5m0 0l-5 5m5-5H6"
                                    />
                                </svg>
                            </Link>
                        </div>
                    </div>

                    {/* DevTools Card */}
                    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 h-full">
                        <div className="p-8 h-full flex flex-col gap-4">
                            <div className="flex items-center gap-3">
                                <div className="bg-purple-100 dark:bg-purple-900 p-3 rounded-lg">
                                    <svg
                                        className="w-6 h-6 text-purple-600 dark:text-purple-400"
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"
                                        />
                                    </svg>
                                </div>
                                <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                                    DevTools
                                </h3>
                            </div>
                            <p className="text-gray-600 dark:text-gray-300 text-sm text-left flex-grow leading-relaxed">
                                Test conversation storage and search with performance monitoring. View latency metrics in real-time.
                            </p>
                            <Link
                                to="/devtools"
                                className="inline-flex items-center px-4 py-2 bg-purple-600 text-white font-medium rounded-lg hover:bg-purple-700 transition-colors duration-200 text-sm"
                            >
                                Open Tools
                                <svg
                                    className="ml-2 w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M13 7l5 5m0 0l-5 5m5-5H6"
                                    />
                                </svg>
                            </Link>
                        </div>
                    </div>

                    {/* Benchmarks Card */}
                    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 h-full">
                        <div className="p-8 h-full flex flex-col gap-4">
                            <div className="flex items-center gap-3">
                                <div className="bg-blue-100 dark:bg-blue-900 p-3 rounded-lg">
                                    <svg
                                        className="w-6 h-6 text-blue-600 dark:text-blue-400"
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                                        />
                                    </svg>
                                </div>
                                <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                                    Benchmarks
                                </h3>
                            </div>
                            <p className="text-gray-600 dark:text-gray-300 text-sm text-left flex-grow leading-relaxed">
                                Run automated benchmark tests to evaluate extraction quality, search relevance, and memory evolution.
                            </p>
                            <Link
                                to="/benchmarks"
                                className="inline-flex items-center px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors duration-200 text-sm"
                            >
                                Run Benchmarks
                                <svg
                                    className="ml-2 w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M13 7l5 5m0 0l-5 5m5-5H6"
                                    />
                                </svg>
                            </Link>
                        </div>
                    </div>

                    {/* Activity Monitor Card */}
                    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 h-full">
                        <div className="p-8 h-full flex flex-col gap-4">
                            <div className="flex items-center gap-3">
                                <div className="bg-teal-100 dark:bg-teal-900 p-3 rounded-lg">
                                    <svg
                                        className="w-6 h-6 text-teal-600 dark:text-teal-400"
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                                        />
                                    </svg>
                                </div>
                                <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                                    Activity Monitor
                                </h3>
                            </div>
                            <p className="text-gray-600 dark:text-gray-300 text-sm text-left flex-grow leading-relaxed">
                                Monitor running extractions, pending tasks, and recent activity. Track progress in real-time with auto-refresh.
                            </p>
                            <Link
                                to="/activity-monitor"
                                className="inline-flex items-center px-4 py-2 bg-teal-600 text-white font-medium rounded-lg hover:bg-teal-700 transition-colors duration-200 text-sm"
                            >
                                View Activity
                                <svg
                                    className="ml-2 w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M13 7l5 5m0 0l-5 5m5-5H6"
                                    />
                                </svg>
                            </Link>
                        </div>
                    </div>
                </div>

                {/* Core Features */}
                <div className="bg-gray-50 dark:bg-gray-800 rounded-lg shadow-md p-8">
                    <h3 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6">
                        Core Features
                    </h3>
                    <div className="grid md:grid-cols-3 gap-6">
                        <div className="text-center">
                            <div className="bg-purple-100 p-3 rounded-lg inline-block mb-4">
                                <svg
                                    className="w-6 h-6 text-purple-600"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"
                                    />
                                </svg>
                            </div>
                            <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                                Store Conversations
                            </h4>
                            <p className="text-sm text-gray-600 dark:text-gray-300">
                                Store raw conversation turns with instant embedding (&lt;100ms)
                            </p>
                        </div>
                        <div className="text-center">
                            <div className="bg-orange-100 p-3 rounded-lg inline-block mb-4">
                                <svg
                                    className="w-6 h-6 text-orange-600"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                                    />
                                </svg>
                            </div>
                            <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                                Search Conversations
                            </h4>
                            <p className="text-sm text-gray-600 dark:text-gray-300">
                                Fast semantic search with direct embedding (100-300ms)
                            </p>
                        </div>
                        <div className="text-center">
                            <div className="bg-indigo-100 p-3 rounded-lg inline-block mb-4">
                                <svg
                                    className="w-6 h-6 text-indigo-600"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M13 10V3L4 14h7v7l9-11h-7z"
                                    />
                                </svg>
                            </div>
                            <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">
                                Perfect Recall
                            </h4>
                            <p className="text-sm text-gray-600 dark:text-gray-300">
                                No lossy extraction - store everything, search instantly
                            </p>
                        </div>
                    </div>
                </div>
            </main>

                {/* Footer - floating with rounded edges */}
                <footer className="bg-gray-50 dark:bg-gray-800 rounded-lg shadow-sm mx-2 mb-2 py-8">
                    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
                        <p className="text-gray-600 dark:text-gray-400">
                            Mnemosyne - AI Memory Service • Built with Django &
                            React
                        </p>
                    </div>
                </footer>
            </div>
        </div>
    );
};

export default HomePage;
