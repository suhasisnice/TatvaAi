import { NavLink } from "react-router-dom";
import { ShieldCheck, LogOut } from "lucide-react";
import { api } from "../lib/api";
import type { Session } from "../lib/api";

export default function Shell({ session, children }: { session: Session; children: React.ReactNode }) {
  const showBanner = session.role !== "institution";

  function logout() {
    api.logout();
    window.location.href = "/";
  }

  return (
    <div className="app-shell">
      <div className="topbar">
        <div className="brand">
          <ShieldCheck size={22} />
          <div>
            TatvaAI
            <small>PramaanAI &mdash; AICTE application validation prototype</small>
          </div>
        </div>
        {session.role === "officer" && (
          <nav className="nav">
            <NavLink to="/officer" end>Review queue</NavLink>
            <NavLink to="/officer/audit">Audit log</NavLink>
          </nav>
        )}
        <div className="right">
          <span className="role-pill">{session.role}</span>
          <span>{session.name}</span>
          <button className="logout" onClick={logout}><LogOut size={14} /> Log out</button>
        </div>
      </div>
      {showBanner && (
        <div className="banner">Decision support only. Final decisions rest with competent AICTE authorities.</div>
      )}
      <div className="content">{children}</div>
    </div>
  );
}
