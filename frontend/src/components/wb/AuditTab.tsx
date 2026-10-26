import { J } from "../../api";
import { useApi } from "../../hooks";
import { Loading } from "../../ui";

export default function AuditTab({ appId }: { appId: number }) {
  const a = useApi<J[]>(`/audit?application_id=${appId}&limit=300`);
  return (
    <section className="card">
      <h2>Audit trail for this application</h2>
      <p className="muted">Append-only, hash-chained. The chain is verified on the Audit log page.</p>
      {a.loading && <Loading />}
      <table>
        <thead><tr><th>#</th><th>Time (UTC)</th><th>Actor</th><th>Action</th><th>Details</th></tr></thead>
        <tbody>
          {(a.data ?? []).map((r) => (
            <tr key={r.seq}><td>{r.seq}</td><td className="small">{r.ts.slice(0, 19).replace("T", " ")}</td><td className="small">{r.actor}</td><td><code>{r.action}</code></td>
              <td className="small">{r.entity} · {Object.entries(r.payload).filter(([k]) => k !== "application_id").map(([k, v]) => `${k}: ${String(v).slice(0, 60)}`).join(" · ")}</td></tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
