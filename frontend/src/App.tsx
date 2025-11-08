import React from "react";
import { Route, BrowserRouter as Router, Routes } from "react-router-dom";
import DevToolsPage from "./pages/DevToolsPage";
import HomePage from "./pages/HomePage";
import SettingsPage from "./pages/SettingsPage";

const App: React.FC = () => {
    return (
        <Router>
            <div className="App">
                <Routes>
                    <Route path="/" element={<HomePage />} />
                    {/* Import temporarily disabled - will be updated for Phase 1 */}
                    {/* <Route path="/import" element={<ImportPage />} /> */}
                    <Route path="/devtools" element={<DevToolsPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                </Routes>
            </div>
        </Router>
    );
};

export default App;
