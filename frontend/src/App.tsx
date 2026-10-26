import { useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { api } from "./lib/api";
import Shell from "./components/Shell";
import Login from "./pages/Login";
import MyApplications from "./pages/institution/MyApplications";
import ApplicationDetail from "./pages/institution/ApplicationDetail";
import Queue from "./pages/officer/Queue";
import Workbench from "./pages/officer/Workbench";
import AuditLog from "./pages/officer/AuditLog";
import InspectionList from "./pages/inspector/InspectionList";

export default function App() {
  const [session, setSession] = useState(api.getSession());

  function refresh() {
    setSession(api.getSession());
  }

  if (!session) {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="*" element={<Login onLoggedIn={refresh} />} />
        </Routes>
      </BrowserRouter>
    );
  }

  return (
    <BrowserRouter>
      <Shell session={session}>
        <Routes>
          <Route path="/login" element={<Navigate to="/" />} />
          {session.role === "institution" && (
            <>
              <Route path="/institution" element={<MyApplications />} />
              <Route path="/institution/applications/:id" element={<ApplicationDetail />} />
              <Route path="*" element={<Navigate to="/institution" />} />
            </>
          )}
          {session.role === "officer" && (
            <>
              <Route path="/officer" element={<Queue />} />
              <Route path="/officer/applications/:id" element={<Workbench />} />
              <Route path="/officer/audit" element={<AuditLog />} />
              <Route path="*" element={<Navigate to="/officer" />} />
            </>
          )}
          {session.role === "inspector" && (
            <>
              <Route path="/inspector" element={<InspectionList />} />
              <Route path="*" element={<Navigate to="/inspector" />} />
            </>
          )}
        </Routes>
      </Shell>
    </BrowserRouter>
  );
}
