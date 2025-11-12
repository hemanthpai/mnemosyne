import React, { useRef, useState, useEffect } from "react";
import { Route, BrowserRouter as Router, Routes } from "react-router-dom";
import { ThemeProvider } from "./contexts/ThemeContext";
import { SidebarProvider, useSidebar } from "./contexts/SidebarContext";
import Sidebar from "./components/Sidebar";
import DevToolsPage from "./pages/DevToolsPage";
import HomePage from "./pages/HomePage";
import ImportPage from "./pages/ImportPage";
import KnowledgeGraphPage from "./pages/KnowledgeGraphPage";
import NotesPage from "./pages/NotesPage";
import SettingsPage from "./pages/SettingsPage";
import BenchmarksPage from "./pages/BenchmarksPage";
import ActivityMonitorPage from "./pages/ActivityMonitorPage";

const AppContent: React.FC = () => {
    const { isSidebarOpen, toggleSidebar } = useSidebar();
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const [scrollY, setScrollY] = useState(0);

    useEffect(() => {
        const handleScroll = () => {
            if (scrollContainerRef.current) {
                setScrollY(scrollContainerRef.current.scrollTop);
            }
        };

        const scrollContainer = scrollContainerRef.current;
        if (scrollContainer) {
            scrollContainer.addEventListener('scroll', handleScroll);
            return () => scrollContainer.removeEventListener('scroll', handleScroll);
        }
    }, []);

    return (
        <div className="h-screen overflow-hidden bg-gray-100 dark:bg-gray-900">
            <Sidebar isOpen={isSidebarOpen} onToggle={toggleSidebar} scrollY={scrollY} />

            <div ref={scrollContainerRef} className="h-full overflow-auto">
                <Routes>
                    <Route path="/" element={<HomePage />} />
                    <Route path="/import" element={<ImportPage />} />
                    <Route path="/notes" element={<NotesPage />} />
                    <Route path="/graph" element={<KnowledgeGraphPage />} />
                    <Route path="/devtools" element={<DevToolsPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="/benchmarks" element={<BenchmarksPage />} />
                    <Route path="/activity-monitor" element={<ActivityMonitorPage />} />
                </Routes>
            </div>
        </div>
    );
};

const App: React.FC = () => {
    return (
        <ThemeProvider>
            <SidebarProvider>
                <Router>
                    <AppContent />
                </Router>
            </SidebarProvider>
        </ThemeProvider>
    );
};

export default App;
