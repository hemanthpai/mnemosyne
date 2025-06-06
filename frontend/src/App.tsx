import React from "react";
import { Route, BrowserRouter as Router, Routes } from "react-router-dom";
import DevToolsPage from "./pages/DevToolsPage";
import HomePage from "./pages/HomePage";
import MemoriesPage from "./pages/MemoriesPage";
import MemoryDetailPage from "./pages/MemoryDetailPage"; // Add this import
import MemoryStatsPage from "./pages/MemoryStatsPage"; // Add this import
import SettingsPage from "./pages/SettingsPage";

const App: React.FC = () => {
    return (
        <Router>
            <div className="App">
                <Routes>
                    <Route path="/" element={<HomePage />} />
                    <Route path="/memories" element={<MemoriesPage />} />
                    <Route path="/devtools" element={<DevToolsPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="/stats" element={<MemoryStatsPage />} />{" "}
                    <Route path="/memory/:id" element={<MemoryDetailPage />} />
                </Routes>
            </div>
        </Router>
    );
};

export default App;
