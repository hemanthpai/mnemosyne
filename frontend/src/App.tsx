import React from "react";
import { Route, BrowserRouter as Router, Routes } from "react-router-dom";
import { ThemeProvider } from "./contexts/ThemeContext";
import DevToolsPage from "./pages/DevToolsPage";
import HomePage from "./pages/HomePage";
import ImportPage from "./pages/ImportPage";
import KnowledgeGraphPage from "./pages/KnowledgeGraphPage";
import NotesPage from "./pages/NotesPage";
import SettingsPage from "./pages/SettingsPage";

const App: React.FC = () => {
    return (
        <ThemeProvider>
            <Router>
                <div className="App">
                    <Routes>
                        <Route path="/" element={<HomePage />} />
                        <Route path="/import" element={<ImportPage />} />
                        <Route path="/notes" element={<NotesPage />} />
                        <Route path="/graph" element={<KnowledgeGraphPage />} />
                        <Route path="/devtools" element={<DevToolsPage />} />
                        <Route path="/settings" element={<SettingsPage />} />
                    </Routes>
                </div>
            </Router>
        </ThemeProvider>
    );
};

export default App;
