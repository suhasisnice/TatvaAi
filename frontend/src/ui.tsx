import { AlertTriangle, CalendarX, CheckCircle2, ClipboardCheck, Hourglass, ShieldAlert, ShieldCheck, WifiOff } from "lucide-react";
import { ReactNode } from "react";
import { J } from "./api";

// Risk tiers: the text label is always shown next to the colour.
export const TIER: Record<string, { label: string; cls: string }> = {
  GREEN: { label: "No risk", cls: "green" }, AMBER: { label: "Medium risk", cls: "amber" }, RED: { label: "High risk", cls: "red" },
};

export function RiskChip({ tier, score }: { tier?: string | null; score?: number | null }) {
  if (!tier) return <span className="chip grey">Not scored</span>;
  const t = TIER[tier];
  return <span className={`chip tier ${t.cls}`} title={`${tier} = ${t.label}`}>{tier} · {t.label}{score != null && <span className="score"> · {score}</span>}</span>;
}

// The six verification statuses, each with its own icon and text.
export const VSTATUS: Record<string, { label: string; cls: string; icon: ReactNode }> = {
  VERIFIED: { label: "Verified", cls: "green", icon: <ShieldCheck size={14} aria-hidden /> },
  MISMATCH_DETECTED: { label: "Mismatch detected", cls: "red", icon: <ShieldAlert size={14} aria-hidden /> },
  EXPIRED: { label: "Expired", cls: "amber", icon: <CalendarX size={14} aria-hidden /> },
  VERIFICATION_PENDING: { label: "Verification pending", cls: "blue", icon: <Hourglass size={14} aria-hidden /> },
  SOURCE_UNAVAILABLE: { label: "Source unavailable", cls: "grey", icon: <WifiOff size={14} aria-hidden /> },
  MANUAL_REVIEW_REQUIRED: { label: "Manual review required", cls: "purple", icon: <ClipboardCheck size={14} aria-hidden /> },
};
export function StatusBadge({ status }: { status: string }) {
  const s = VSTATUS[status] ?? { label: status, cls: "grey", icon: null };
  return <span className={`chip ${s.cls}`}>{s.icon}{s.label}</span>;
}

export function SeverityChip({ severity }: { severity: string }) {
  const cls = { CRITICAL: "red", MAJOR: "amber", MINOR: "blue", INFO: "grey" }[severity] ?? "grey";
  return <span className={`chip ${cls}`}>{severity}</span>;
}

/** The feature map: the five engines roll up into two checking features. */
export const FEATURES: Record<number, string> = { 1: "Feature 1 · Handbook rule checker", 2: "Feature 2 · Document & consistency check" };

export const MockTag = () => <span className="mock" title="Simulated external system">MOCK</span>;
export const Prelim = () => <span className="chip purple" title="Forensic indicator">Preliminary indicator — requires human verification</span>;

export function RuleStatus({ status }: { status: string }) {
  const m: Record<string, string> = { PASS: "green", FAIL: "red", INSUFFICIENT_EVIDENCE: "grey" };
  return <span className={`chip ${m[status] ?? "grey"}`}>{status === "PASS" ? <CheckCircle2 size={14} aria-hidden /> : status === "FAIL" ? <AlertTriangle size={14} aria-hidden /> : null}{status.replace("_", " ")}</span>;
}

export const cite = (c?: J) => (c ? `${c.source}, ${c.clause}, p. ${c.page}` : "");
export const fmtDate = (s?: string | null) => (s ? s.slice(0, 10) : "—");

export function Loading({ what = "Loading" }: { what?: string }) { return <p role="status" className="muted">{what}…</p>; }
export function ErrorBox({ message }: { message?: string }) { return message ? <p role="alert" className="err">{message}</p> : null; }

export function KPI({ label, value, cls = "" }: { label: string; value: ReactNode; cls?: string }) {
  return <div className={`kpi ${cls}`}><div className="kpi-v">{value}</div><div className="kpi-l">{label}</div></div>;
}

export function Tabs({ tabs, active, onChange }: { tabs: [string, string][]; active: string; onChange: (k: string) => void }) {
  return (
    <div role="tablist" className="tabs" aria-label="Workbench sections">
      {tabs.map(([k, label]) => (
        <button key={k} role="tab" id={`tab-${k}`} aria-selected={active === k} aria-controls={`panel-${k}`} tabIndex={active === k ? 0 : -1}
          className={active === k ? "on" : ""} onClick={() => onChange(k)}
          onKeyDown={(e) => {
            const i = tabs.findIndex(([x]) => x === active);
            if (e.key === "ArrowRight") onChange(tabs[(i + 1) % tabs.length][0]);
            if (e.key === "ArrowLeft") onChange(tabs[(i + tabs.length - 1) % tabs.length][0]);
          }}>{label}</button>
      ))}
    </div>
  );
}
