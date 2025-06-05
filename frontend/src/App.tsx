import React from "react";
import { Route, BrowserRouter as Router, Routes } from "react-router-dom";
import DevToolsPage from "./pages/DevToolsPage";
import HomePage from "./pages/HomePage";
import MemoriesPage from "./pages/MemoriesPage";
import MemoryDetailPage from "./pages/MemoryDetailPage";
import SettingsPage from "./pages/SettingsPage";

const App: React.FC = () => {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/memories" element={<MemoriesPage />} />
        <Route path="/memory/:id" element={<MemoryDetailPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/devtools" element={<DevToolsPage />} />
      </Routes>
    </Router>
  );
};

export default App;