import { Home } from "lucide-react";
import { ReactNode, useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";

const SIZES = [{ label: "A-", zoom: 0.92 }, { label: "A", zoom: 1 }, { label: "A+", zoom: 1.12 }];

/** Text-size control like the AICTE site's A- A A+; remembers the choice. */
function TextSize() {
  const [zoom, setZoom] = useState(() => { try { return Number(localStorage.getItem("text_zoom")) || 1; } catch { return 1; } });
  useEffect(() => {
    document.getElementById("root")?.style.setProperty("zoom", String(zoom));
    try { localStorage.setItem("text_zoom", String(zoom)); } catch { /* storage unavailable */ }
  }, [zoom]);
  return (
    <span className="textsize" role="group" aria-label="Text size">
      <span>Text Size</span>
      {SIZES.map((s) => <button key={s.label} type="button" aria-pressed={zoom === s.zoom} onClick={() => setZoom(s.zoom)}>{s.label}</button>)}
    </span>
  );
}

/** Dark utility strip: date and accessibility links on the left; text size, alerts, account on the right. */
export function UtilBar({ children }: { children?: ReactNode }) {
  const today = new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  return (
    <div className="util">
      <div className="wrap row between">
        <span className="util-left"><a href="#main" className="skip">Skip to main content</a><span>{today}</span></span>
        <span className="util-right"><TextSize />{children}</span>
      </div>
    </div>
  );
}

/** White masthead with the product mark (our own, not an AICTE emblem). */
export function Masthead() {
  return (
    <div className="masthead">
      <div className="wrap row between">
        <Link to="/" className="mast-brand" aria-label="TatvaAI home">
          <svg width="52" height="52" viewBox="0 0 52 52" aria-hidden="true"><circle cx="26" cy="26" r="24" fill="#005aaa" /><circle cx="26" cy="26" r="19" fill="none" stroke="#fff" strokeWidth="1.5" /><path d="M14 18h24M26 18v19" stroke="#fff" strokeWidth="4" strokeLinecap="round" /><circle cx="26" cy="26" r="3" fill="#f26a1b" /></svg>
          <span><b>TatvaAI</b><small>AI-powered application validation, document authentication &amp; regulatory compliance verification</small></span>
        </Link>
        <span className="mast-note">Smart India Hackathon 2026 · SIH26261<br />Prototype for the AICTE Regulation Bureau · synthetic data only</span>
      </div>
    </div>
  );
}

/** Orange menu bar: home icon, then the role's pages in capitals. */
export function MenuBar({ home, items }: { home: string; items: [string, string][] }) {
  return (
    <nav className="menubar" aria-label="Main">
      <div className="wrap row">
        <NavLink to={home} end className="home" aria-label="Home"><Home size={20} aria-hidden /></NavLink>
        {items.map(([to, label]) => <NavLink key={to} to={to} end={to.split("/").length <= 2}>{label}</NavLink>)}
      </div>
    </nav>
  );
}

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="wrap">
        <p><b>TatvaAI</b> · decision support only. Final decisions rest with competent AICTE authorities. The software never approves, rejects or penalises.</p>
        <p className="muted-light">All institutions, people and documents are synthetic; every external source (SHCIL, DigiLocker, ICAI, state portals, AICTE records) is a clearly labelled MOCK.</p>
      </div>
    </footer>
  );
}
