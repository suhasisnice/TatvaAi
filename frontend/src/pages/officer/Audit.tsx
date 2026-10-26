import { CheckCircle2, Download, ShieldX } from "lucide-react";
import { useState } from "react";
import { download, J } from "../../api";
import { useApi } from "../../hooks";
import { ErrorBox, Loading } from "../../ui";

export default function Audit() {
  const [action, setAction] = useState("");
  const [offset, setOffset] = useState(0);
  const v = useApi<J>("/audit/verify");
  const rows = useApi<J[]>(`/audit?limit=50&offset=${offset}${action ? `&action=${encodeURIComponent(action)}` : ""}`);
  const [err, setErr] = useState("");
  const ok = v.data?.intact;
  return (
    <>
      <h1>Audit log</h1>
      {v.loading && !v.data ? <Loading what="Verifying chain" /> : v.data && (
        <div className={`chain ${ok ? "ok" : "broken"}`} role={ok ? "status" : "alert"}>
          {ok ? <CheckCircle2 size={34} aria-hidden /> : <ShieldX size={34} aria-hidden />}
          <div>
            <div className="chain-title">{ok ? "Chain intact" : `Broken at entry ${v.data.broken_at}`}</div>
            <div>{ok ? `${v.data.entries} entries verified. Head hash ${v.data.head?.slice(0, 16)}…` : `${v.data.reason}. Entries from ${v.data.broken_at} onward cannot be trusted.`}</div>
          </div>
          <button onClick={() => { v.reload(); rows.reload(); }}>Verify again</button>
        </div>
      )}
      <ErrorBox message={err || v.error} />
      <div className="card">
        <div className="row between end">
          <label>Filter by action<select value={action} onChange={(e) => { setAction(e.target.value); setOffset(0); }}><option value="">All</option>
            {["auth", "application", "document", "engine", "verification", "risk", "flag", "rulepack", "report", "user", "mfa"].map((a) => <option key={a}>{a}</option>)}</select></label>
          <button onClick={() => download("/audit/export?format=csv", "audit.csv").catch((e) => setErr(e.message))}><Download size={15} aria-hidden /> Export CSV</button>
        </div>
        <table>
          <thead><tr><th>#</th><th>Time (UTC)</th><th>Actor</th><th>Action</th><th>Entity</th><th>Hash</th></tr></thead>
          <tbody>
            {(rows.data ?? []).map((r) => (
              <tr key={r.seq} className={v.data?.broken_at === r.seq ? "rowfail" : ""}>
                <td>{r.seq}</td><td className="small">{r.ts.slice(0, 19).replace("T", " ")}</td><td className="small">{r.actor}</td><td><code>{r.action}</code></td>
                <td className="small">{r.entity}</td><td className="small mono" title={r.hash}>{r.hash.slice(0, 12)}…</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="row gap">
          <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Newer</button>
          <button disabled={(rows.data?.length ?? 0) < 50} onClick={() => setOffset(offset + 50)}>Older</button>
        </div>
      </div>
    </>
  );
}
