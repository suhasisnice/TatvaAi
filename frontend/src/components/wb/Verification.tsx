import { useState } from "react";
import { J, post } from "../../api";
import { useApi } from "../../hooks";
import { ErrorBox, fmtDate, Loading, MockTag, StatusBadge, VSTATUS } from "../../ui";

export default function Verification({ appId, docs, canConfirm }: { appId: number; docs: J[]; canConfirm: boolean }) {
  const vs = useApi<J[]>(`/applications/${appId}/verifications`);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [err, setErr] = useState("");
  const docType = (id: number | null) => (id ? docs.find((d) => d.id === id)?.doc_type.replaceAll("_", " ") ?? `Document ${id}` : "Application");
  const confirm = async (v: J) => {
    setErr("");
    try { await post(`/verifications/${v.id}/manual`, { note: notes[v.id] ?? "" }); vs.reload(); } catch (e) { setErr((e as Error).message); }
  };
  return (
    <section className="card">
      <h2>Verification with issuing sources</h2>
      <p className="muted">Each row is one check against the original issuer. All sources are simulated in this prototype. If a source is unavailable the check is routed to manual review.</p>
      <div className="legend">{Object.keys(VSTATUS).map((s) => <StatusBadge key={s} status={s} />)}</div>
      {vs.loading && <Loading />}<ErrorBox message={err || vs.error} />
      <table>
        <thead><tr><th>Document</th><th>Source</th><th>Status</th><th>Response summary</th><th>Checked</th></tr></thead>
        <tbody>
          {(vs.data ?? []).map((v) => (
            <tr key={v.id}>
              <td>{docType(v.document_id)}</td>
              <td>{v.source} <MockTag /></td>
              <td><StatusBadge status={v.status} />{v.carried_forward_from && <div className="muted small">carried forward from {v.carried_forward_from}</div>}</td>
              <td>
                {v.response_summary}
                {v.manual_note && <div className="muted small">Officer note: {v.manual_note}</div>}
                {canConfirm && v.status === "MANUAL_REVIEW_REQUIRED" && (
                  <div className="row gap manual">
                    <input aria-label="Manual confirmation note" placeholder="How did you confirm? (call, letter, site visit)" value={notes[v.id] ?? ""} onChange={(e) => setNotes({ ...notes, [v.id]: e.target.value })} />
                    <button disabled={(notes[v.id] ?? "").trim().length < 5} onClick={() => confirm(v)}>Record manual confirmation</button>
                  </div>
                )}
              </td>
              <td>{fmtDate(v.checked_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
