import { useState } from "react";
import { J } from "../../api";
import { useApi } from "../../hooks";
import { cite, Loading, RuleStatus } from "../../ui";

const fmt = (o: J) => Object.entries(o ?? {}).filter(([, v]) => typeof v !== "object").map(([k, v]) => `${k} = ${typeof v === "number" ? +v.toFixed(2) : String(v)}`).join(", ");

export default function Compliance({ appId }: { appId: number }) {
  const rr = useApi<J[]>(`/applications/${appId}/rule-results`);
  const [status, setStatus] = useState("");
  const rows = (rr.data ?? []).filter((r) => !status || r.status === status);
  const counts = (rr.data ?? []).reduce<Record<string, number>>((m, r) => ({ ...m, [r.status]: (m[r.status] ?? 0) + 1 }), {});
  return (
    <section className="card">
      <div className="row between">
        <div><h2>Compliance with the Handbook (rule results)</h2><p className="muted">Every rule shows the numbers used, the result, the Handbook citation and the rule pack version.</p></div>
        <label>Show<select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All ({rr.data?.length ?? 0})</option><option value="FAIL">FAIL ({counts.FAIL ?? 0})</option><option value="PASS">PASS ({counts.PASS ?? 0})</option><option value="INSUFFICIENT_EVIDENCE">INSUFFICIENT_EVIDENCE ({counts.INSUFFICIENT_EVIDENCE ?? 0})</option></select></label>
      </div>
      {rr.loading && <Loading />}
      <table>
        <thead><tr><th>Rule</th><th>Computed values</th><th>Result</th><th>Citation</th><th>Pack</th></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={r.status === "FAIL" ? "rowfail" : ""}>
              <td><strong>{r.title}</strong><div className="muted small">{r.rule_id}{r.scope ? ` · ${r.scope}` : ""}</div></td>
              <td className="small">{fmt({ ...r.inputs, ...r.computed }) || "—"}<div>{r.status === "FAIL" && <b>{r.message}</b>}</div></td>
              <td><RuleStatus status={r.status} /></td>
              <td className="small">{cite(r.citation)}</td>
              <td>{r.rule_pack_version}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
