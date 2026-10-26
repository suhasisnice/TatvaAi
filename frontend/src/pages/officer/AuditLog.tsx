import { useEffect, useState } from "react";
import { ShieldCheck, ShieldAlert, RefreshCw } from "lucide-react";
import { api } from "../../lib/api";

export default function AuditLog() {
  const [entries, setEntries] = useState<any[]>([]);
  const [chain, setChain] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    try {
      const [list, status] = await Promise.all([api.auditLog(), api.auditVerify()]);
      setEntries(list);
      setChain(status);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => { load(); }, []);

  return (
    <div>
      <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0 }}>Audit log</h2>
          <p className="muted small" style={{ margin: "4px 0 0" }}>
            Every login, upload, engine run, decision and inspection is hash-chained: each entry's hash includes the previous one.
          </p>
        </div>
        <button className="btn secondary" onClick={load} disabled={busy}>
          <RefreshCw size={14} /> Verify again
        </button>
      </div>

      {chain && (
        <div className="card" style={{ borderColor: chain.intact ? "var(--green)" : "var(--red)" }}>
          {chain.intact ? (
            <span style={{ color: "var(--green)", fontWeight: 700 }}>
              <ShieldCheck size={16} style={{ verticalAlign: -3 }} /> Chain intact &middot; {chain.entries} entries
            </span>
          ) : (
            <span style={{ color: "var(--red)", fontWeight: 700 }}>
              <ShieldAlert size={16} style={{ verticalAlign: -3 }} /> Broken at entry {chain.broken_at} &middot; {chain.entries} entries
            </span>
          )}
        </div>
      )}

      <div className="card">
        <table>
          <thead><tr><th>#</th><th>Time (UTC)</th><th>Actor</th><th>Action</th><th>Entity</th><th>Hash</th></tr></thead>
          <tbody>
            {entries.map(e => (
              <tr key={e.seq}>
                <td>{e.seq}</td>
                <td className="small">{e.created_at.replace("T", " ").slice(0, 19)}</td>
                <td className="small">{e.actor}</td>
                <td className="small">{e.action}</td>
                <td className="small muted">{e.entity}</td>
                <td className="small muted"><code>{e.hash}</code></td>
              </tr>
            ))}
            {entries.length === 0 && <tr><td colSpan={6} className="muted">No entries.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
