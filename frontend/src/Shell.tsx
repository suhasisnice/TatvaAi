import { Bell, LogOut, ShieldCheck } from "lucide-react";
import { ReactNode, useEffect, useRef, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { api, J, post, User } from "./api";
import { fmtDate, SeverityChip } from "./ui";

const NAV: Record<string, [string, string][]> = {
  institution: [["/institution", "My applications"]],
  officer: [["/officer", "Review queue"], ["/officer/inspections", "Inspections"], ["/officer/rules", "Rule packs"], ["/officer/audit", "Audit log"]],
  inspector: [["/inspector", "Inspection list"]],
};

function Bell_({ user }: { user: User }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<J>({ unread_count: 0, alerts: [] });
  const nav = useNavigate();
  const ref = useRef<HTMLDivElement>(null);
  const load = () => api("/alerts").then(setData).catch(() => undefined);
  useEffect(() => { load(); const t = setInterval(load, 60_000); return () => clearInterval(t); }, []);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const go = async (a: J) => {
    await post(`/alerts/${a.id}/read`).catch(() => undefined);
    setOpen(false);
    load();
    nav(user.role === "institution" ? `/institution/applications/${a.application_id}` : `/officer/applications/${a.application_id}`);
  };
  return (
    <div className="bell" ref={ref}>
      <button aria-label={`Alerts, ${data.unread_count} unread`} aria-expanded={open} onClick={() => setOpen(!open)} className="icon-btn">
        <Bell size={18} aria-hidden />{data.unread_count > 0 && <span className="badge">{data.unread_count}</span>}
      </button>
      {open && (
        <div className="dropdown" role="menu" aria-label="Alerts">
          {data.alerts.length === 0 && <p className="muted pad">No alerts</p>}
          {data.alerts.slice(0, 12).map((a: J) => (
            <button key={a.id} role="menuitem" className={`alert-item ${a.read ? "read" : ""}`} onClick={() => go(a)}>
              <span><SeverityChip severity={a.severity} /> <span className="muted">{a.kind.replace("_", " ")} · {fmtDate(a.created_at)}</span></span>
              <span>{a.message}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Shell({ user, onLogout, children }: { user: User; onLogout: () => void; children: ReactNode }) {
  return (
    <>
      <header className="top">
        <Link to="/" className="brand"><ShieldCheck size={20} aria-hidden /> PramaanAI</Link>
        <nav aria-label="Main">{NAV[user.role].map(([to, label]) => <NavLink key={to} to={to} end={to.split("/").length <= 2}>{label}</NavLink>)}</nav>
        <span className="spacer" />
        <Bell_ user={user} />
        <Link to="/security" className="who" title="Security settings">{user.name} · {user.role}</Link>
        <button className="icon-btn" onClick={onLogout} aria-label="Log out"><LogOut size={18} aria-hidden /></button>
      </header>
      {user.role !== "institution" && <div className="banner" role="note">Decision support only. Final decisions rest with competent AICTE authorities.</div>}
      {user.role === "officer" && !user.mfa_enabled && <div className="banner warn" role="note">Two-factor authentication is not enabled for your account. <Link to="/security">Set it up</Link>.</div>}
      <main>{children}</main>
    </>
  );
}
