import { J } from "../../api";
import { useApi } from "../../hooks";
import { cite, fmtDate, Loading, RiskChip, SeverityChip } from "../../ui";

const PROOF: Record<string, string> = { ISSUER_VERIFIED: "Issuer verified (signature and issuer both confirm)", CRYPTOGRAPHIC: "Cryptographic (valid signature; no issuer confirmation)", FORENSIC_ONLY: "Forensic only (no cryptographic proof)" };

export default function Summary({ app, docs }: { app: J; docs: J[] }) {
  const flags = useApi<J[]>(`/flags?application_id=${app.id}`);
  const risk = app.risk;
  const live = (flags.data ?? []).filter((f) => f.status !== "DISMISSED" && f.severity !== "INFO");
  const byEngine = live.reduce<Record<string, number>>((m, f) => ({ ...m, [f.engine]: (m[f.engine] ?? 0) + 1 }), {});
  return (
    <>
      <section className="card">
        <div className="row between">
          <div><h2>Risk assessment</h2><p className="muted">{risk?.routing_text}. Advice to the officer only; no approval or rejection is made by the system.</p></div>
          <RiskChip tier={risk?.tier} score={risk?.score} />
        </div>
        <table>
          <thead><tr><th>Top reasons (largest contribution first)</th><th>Severity</th><th>Contribution</th></tr></thead>
          <tbody>
            {(risk?.reasons ?? []).map((r: J) => <tr key={r.flag_id}><td>{r.message}{r.forensic && <span className="chip purple">Preliminary indicator</span>}</td><td><SeverityChip severity={r.severity} /></td><td>{r.contribution}</td></tr>)}
            {!risk?.reasons?.length && <tr><td colSpan={3} className="muted">No findings.</td></tr>}
          </tbody>
        </table>
        <p className="muted">Rule pack {risk?.rule_pack_version}. Open findings by engine: {Object.entries(byEngine).map(([k, v]) => `${k} ${v}`).join(" · ") || "none"}.</p>
      </section>
      <section className="card">
        <h2>Documents and proof level</h2>
        <p className="muted">Proof comes first: signatures and issuer checks outrank forensic indicators.</p>
        <table>
          <thead><tr><th>Document</th><th>File</th><th>Digital signature</th><th>Proof level reached</th><th>Verified earlier</th></tr></thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id}>
                <td>{d.doc_type.replaceAll("_", " ")}</td><td>{d.filename}</td><td>{d.dsc_status?.replace("SIGNED_", "").toLowerCase() ?? "—"}</td>
                <td>{d.proof_level ? <span className={`chip ${d.proof_level === "FORENSIC_ONLY" ? "amber" : "green"}`} title={PROOF[d.proof_level]}>{d.proof_level.replace("_", " ")}</span> : "—"}</td>
                <td>{d.carried_forward_from ? `Carried forward from ${d.carried_forward_from}` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {flags.loading && <Loading />}
        <p className="muted small">Citation example: {cite({ source: "APH 2024-27", clause: "Clause 2.3.5", page: 15 })}: a fraudulent document leads to a criminal case against the Director/Principal and the Trust chairman/secretary. Last scored {fmtDate(app.scored_at)}.</p>
      </section>
    </>
  );
}
