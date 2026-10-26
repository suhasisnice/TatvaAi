import { CheckCircle2, CircleDashed, Lock, Upload } from "lucide-react";
import { ChangeEvent, FormEvent, useState } from "react";
import { useParams } from "react-router-dom";
import { api, J, post } from "../../api";
import CourseIntake from "../../components/CourseIntake";
import { useApi } from "../../hooks";
import { ErrorBox, fmtDate, Loading, SeverityChip } from "../../ui";

// Required documents per category (mirrors rulepacks/*/categories.yaml; the server stays the source of truth for the fix-list).
const EOA_DOCS: [string, string][] = [
  ["AFFIDAVIT_2", "Affidavit 2 (Rs 100 e-stamp, notarised, DSC-signed)"], ["TER_RECEIPT", "TER payment receipt"], ["OCCUPANCY_CERTIFICATE", "Occupancy / completion certificate"],
  ["STRUCTURAL_STABILITY_CERTIFICATE", "Structural stability certificate (only if a building is over 30 years old)"], ["FIRE_SAFETY_CERTIFICATE", "Fire safety certificate"],
  ["SATELLITE_MAP", "Satellite map with main-entrance latitude/longitude"], ["AUDITED_ACCOUNTS", "Audited statement of accounts"],
  ["FACULTY_LIST", "Faculty list (CSV)"], ["INFRA_PHOTO", "Infrastructure photos (classroom, lab, library)"],
  // Land documents are not on the EoA list (APH Annexure-2, 2.1, p. 81) but are still checked when uploaded.
];
const REQUIRED: Record<string, [string, string][]> = {
  EOA: EOA_DOCS,
  INCREASE_IN_INTAKE: [...EOA_DOCS, ["AFFIDAVIT_8", "Affidavit 8"], ["TRUST_RESOLUTION", "Trust resolution (Format 3)"]],
  NAME_CHANGE_INSTITUTION: [["NOC_AFFILIATING_UNIVERSITY", "NOC from affiliating university (Format 2)"], ["TRUST_RESOLUTION", "Trust resolution (Format 3)"]],
};
const SIG: Record<string, [string, string]> = { SIGNED_VALID: ["green", "Signed"], SIGNED_MODIFIED: ["amber", "Signed (changed after signing)"], SIGNED_INVALID: ["red", "Signature invalid"],
  SIGNED_UNTRUSTED: ["amber", "Signer not trusted"], UNSIGNED: ["grey", "Not signed"] };

export default function InstApp() {
  const { id } = useParams();
  const app = useApi<J>(`/applications/${id}`);
  const docs = useApi<J[]>(`/applications/${id}/documents`);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [fix, setFix] = useState<J>(null);
  const [edit, setEdit] = useState<J>({});
  const a = app.data;
  if (app.loading || !a) return app.error ? <ErrorBox message={app.error} /> : <Loading />;
  const form = a.form_data ?? {};
  const locked: boolean = a.locked;
  const have = new Set((docs.data ?? []).map((d) => d.doc_type));
  const required = REQUIRED[a.category] ?? EOA_DOCS;

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label); setErr(""); setMsg("");
    try { await fn(); } catch (e) { setErr((e as Error).message); } finally { setBusy(""); }
  };
  const upload = (e: ChangeEvent<HTMLInputElement>) => run("upload", async () => {
    for (const f of Array.from(e.target.files ?? [])) {
      const fd = new FormData(); fd.append("file", f);
      const d = await api<J>(`/applications/${id}/documents`, { method: "POST", body: fd });
      setMsg((m) => `${m}${f.name} → recognised as ${d.doc_type.replaceAll("_", " ")} (${Math.round(d.classification_confidence * 100)}% sure). `);
    }
    e.target.value = "";
    docs.reload();
  });
  const precheck = () => run("precheck", async () => {
    const started = await post<J>(`/applications/${id}/precheck`);
    const job = await api<J>(`/precheck/jobs/${started.job_id}`);
    if (job.status === "FAILED") throw new Error(job.error ?? "Pre-check failed");
    setFix(job.fix_list);
  });
  const saveDetails = (e: FormEvent) => { e.preventDefault(); return run("save", async () => {
    await api(`/applications/${id}`, { method: "PATCH", body: JSON.stringify({ form: edit }) });
    setMsg("Details saved."); setEdit({}); app.reload();
  }); };
  const submit = () => {
    if (!confirm("Submit this application?\n\nAfter submission you cannot edit it. The Regulation Bureau can reopen an application only once.")) return;
    return run("submit", async () => { await post(`/applications/${id}/submit`); app.reload(); setMsg("Submitted. The application is now locked."); });
  };

  return (
    <>
      <div className="row between">
        <h1>{a.academic_year} · {a.category.replaceAll("_", " ")}</h1>
        <span className={`chip ${locked ? "grey" : "blue"}`}>{locked && <Lock size={13} aria-hidden />}{a.status}{locked ? " (locked, no edits)" : ""}</span>
      </div>
      <p className="muted">{a.institution_name} · {a.state}</p>
      {msg && <p role="status" className="ok">{msg}</p>}<ErrorBox message={err} />

      <section className="card">
        <h2>Application details</h2>
        <dl className="kv">
          <dt>Trust / Society</dt><dd>{form.institution?.trust_name}</dd>
          <dt>Address</dt><dd>{form.institution?.address}</dd>
          <dt>Survey number</dt><dd>{form.institution?.survey_no}</dd>
          <dt>Signatory</dt><dd>{form.signatory?.name}</dd>
          <dt>Declared full-time faculty</dt><dd>{form.faculty?.declared_full_time}</dd>
          <dt>Declared built-up area</dt><dd>{form.declared_built_up_total_m2?.toLocaleString()} sq m</dd>
        </dl>
        {!locked && (
          <form onSubmit={saveDetails} className="row gap end">
            <label>Address<input defaultValue={form.institution?.address} onChange={(e) => setEdit({ ...edit, institution: { ...edit.institution, address: e.target.value } })} /></label>
            <label>Signatory<input defaultValue={form.signatory?.name} onChange={(e) => setEdit({ ...edit, signatory: { name: e.target.value, designation: form.signatory?.designation } })} /></label>
            <label>Declared faculty<input type="number" min={0} defaultValue={form.faculty?.declared_full_time} onChange={(e) => setEdit({ ...edit, faculty: { declared_full_time: Number(e.target.value) } })} /></label>
            <button disabled={!Object.keys(edit).length || !!busy}>Save details</button>
          </form>
        )}
      </section>

      <CourseIntake appId={Number(id)} programmes={form.programmes ?? []} locked={locked} onSaved={app.reload} />

      <section className="card">
        <div className="row between">
          <h2>Documents</h2>
          {!locked && <label className="upload"><Upload size={16} aria-hidden /> Upload documents (PDF, JPG, PNG, CSV)<input type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.csv" onChange={upload} disabled={!!busy} /></label>}
        </div>
        <table>
          <thead><tr><th>Required document</th><th>Status</th><th>Uploaded file</th><th>Digital signature</th></tr></thead>
          <tbody>
            {required.map(([t, label]) => {
              const mine = (docs.data ?? []).filter((d) => d.doc_type === t);
              return (
                <tr key={t}>
                  <td>{label}</td>
                  <td>{have.has(t) ? <span className="chip green"><CheckCircle2 size={14} aria-hidden />Uploaded ({mine.length})</span> : <span className="chip grey"><CircleDashed size={14} aria-hidden />Not uploaded</span>}</td>
                  <td>{mine.map((d) => d.filename).join(", ") || "—"}</td>
                  <td>{mine.map((d) => { const [c, l] = SIG[d.dsc_status] ?? ["grey", "—"]; return <span key={d.id} className={`chip ${c}`}>{d.content_type === "application/pdf" ? l : "n/a"}</span>; })}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {(docs.data ?? []).some((d) => d.doc_type === "UNKNOWN") && <p className="err">Some files could not be recognised. Check that they are the right documents.</p>}
      </section>

      <section className="card">
        <div className="row between">
          <div><h2>Pre-check</h2><p className="muted">Checks your documents against the Handbook rules and shows what to fix before you submit.</p></div>
          {!locked && <button className="primary" onClick={precheck} disabled={!!busy}>{busy === "precheck" ? "Checking…" : "Run pre-check"}</button>}
        </div>
        {fix && (
          <>
            {fix.total === 0 ? <p className="ok">No issues found. You can submit.</p> : fix.groups.map((g: J) => (
              <div key={g.severity} className="fixgroup">
                <h3><SeverityChip severity={g.severity} /> {g.severity === "CRITICAL" ? "Must fix" : g.severity === "MAJOR" ? "Should fix before submitting" : "Minor"}</h3>
                {g.items.map((i: J) => (
                  <article key={i.flag_id} className="fixitem">
                    <strong>{i.message}</strong>
                    <p><b>How to fix:</b> {i.how_to_fix}</p>
                    {i.citation && <p className="muted">Reference: {i.citation}</p>}
                  </article>
                ))}
              </div>
            ))}
            {fix.waiting_for_officer > 0 && <p className="muted">{fix.waiting_for_officer} item(s) need no action from you: an officer will confirm them directly with the issuing authority.</p>}
          </>
        )}
      </section>

      {!locked && <div className="row end"><button className="primary big" onClick={submit} disabled={!!busy}>Submit application (locks editing)</button></div>}
      {locked && <p className="muted">Submitted {fmtDate(a.submitted_at)}. {a.reopen_count ? "This application was already reopened once." : "It can be reopened once by the Regulation Bureau."}</p>}
    </>
  );
}
