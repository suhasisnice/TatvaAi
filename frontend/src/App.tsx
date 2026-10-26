import { lazy, Suspense, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { api, hasToken, HOME, logout, Role, User } from "./api";
import Login from "./pages/Login";
import Security from "./pages/Security";
import Shell from "./Shell";
import { Loading } from "./ui";

const InstHome = lazy(() => import("./pages/institution/Home"));
const InstApp = lazy(() => import("./pages/institution/Application"));
const Queue = lazy(() => import("./pages/officer/Queue"));
const Workbench = lazy(() => import("./pages/officer/Workbench"));
const Inspections = lazy(() => import("./pages/officer/Inspections"));
const Rules = lazy(() => import("./pages/officer/Rules"));
const Audit = lazy(() => import("./pages/officer/Audit"));

function Guard({ user, roles, children }: { user: User | null; roles: Role[]; children: JSX.Element }) {
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role)) return <Navigate to={HOME[user.role]} replace />;
  return <Shell user={user} onLogout={() => { logout(); location.href = "/login"; }}><Suspense fallback={<Loading />}>{children}</Suspense></Shell>;
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!hasToken()) return setReady(true);
    api<User>("/auth/me").then(setUser).catch(logout).finally(() => setReady(true));
  }, []);
  if (!ready) return <Loading />;
  const all: Role[] = ["institution", "officer", "inspector"];
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={user ? <Navigate to={HOME[user.role]} replace /> : <Login onLogin={setUser} />} />
        <Route path="/institution" element={<Guard user={user} roles={["institution"]}><InstHome /></Guard>} />
        <Route path="/institution/applications/:id" element={<Guard user={user} roles={["institution"]}><InstApp /></Guard>} />
        <Route path="/officer" element={<Guard user={user} roles={["officer"]}><Queue /></Guard>} />
        <Route path="/officer/applications/:id" element={<Guard user={user} roles={["officer"]}><Workbench user={user!} /></Guard>} />
        <Route path="/officer/inspections" element={<Guard user={user} roles={["officer"]}><Inspections /></Guard>} />
        <Route path="/inspector" element={<Guard user={user} roles={["inspector"]}><Inspections canDecide /></Guard>} />
        <Route path="/officer/rules" element={<Guard user={user} roles={["officer"]}><Rules /></Guard>} />
        <Route path="/officer/audit" element={<Guard user={user} roles={["officer"]}><Audit /></Guard>} />
        <Route path="/security" element={<Guard user={user} roles={all}><Security user={user!} onChange={setUser} /></Guard>} />
        <Route path="*" element={<Navigate to={user ? HOME[user.role] : "/login"} replace />} />
      </Routes>
    </BrowserRouter>
  );
}
