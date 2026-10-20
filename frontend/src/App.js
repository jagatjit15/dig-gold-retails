import React, { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "@/App.css";
import "@/index.css";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Login from "@/pages/Login";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Inventory from "@/pages/Inventory";
import Masters from "@/pages/Masters";
import StockAudit from "@/pages/StockAudit";
import LabelPrint from "@/pages/LabelPrint";
import AuditLog from "@/pages/AuditLog";
import ScanLookup from "@/pages/ScanLookup";

function Protected({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function ThemeBoot() {
  useEffect(() => {
    const t = localStorage.getItem("swarna_theme") || "light";
    document.documentElement.classList.toggle("dark", t === "dark");
  }, []);
  return null;
}

function App() {
  return (
    <AuthProvider>
      <ThemeBoot />
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <Protected>
                <Layout />
              </Protected>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="inventory" element={<Inventory />} />
            <Route path="scan" element={<ScanLookup />} />
            <Route path="audit" element={<StockAudit />} />
            <Route path="masters" element={<Masters />} />
            <Route path="labels" element={<LabelPrint />} />
            <Route path="audit-log" element={<AuditLog />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-right" />
    </AuthProvider>
  );
}

export default App;
