import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Upload, PlayCircle, Send, CheckCircle2, FileText } from "lucide-react";
import { api } from "../../lib/api";
import { TierBadge } from "../../components/Badges";

const REQUIRED_DOCS = [
  "AFFIDAVIT_2", "TER_RECEIPT", "OCCUPANCY_CERTIFICATE", "FIRE_SAFETY_CERTIFICATE",
  "SATELLITE_MAP", "AUDITED_ACCOUNTS", "FACULTY_LIST", "INFRA_PHOTO",
];

export default function ApplicationDetail() {
  const { id } = useParams();
  const [app, setApp] = useState<any>(null);
  const [fixList, setFixList] = useState<any>(null);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [confirmingSubmit, setConfirmingSubmit] = useState(false);

  function load() {
    api.getApplication(Number(id)).then(setApp);
  }
  useEffect(load, [id]);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy("upload");
    try {
      await api.uploadDocument(Number(id), file);
      load();
    } catch (err: any) {
      setMsg(err.message);
    } finally {
      setBusy("");
      e.target.value = "";
    }
  }

  async function runPrecheck() {
    setBusy("precheck");
    try {
      const result = await api.precheck(Number(id));
      setFixList(result);
      load();
    } finally {
      setBusy("");
    }
  }

  async function submit() {
    setBusy("submit");
    try {
      await api.submit(Number(id));
      load();
      setMsg("Application submitted.");
      setConfirmingSubmit(false);
    } catch (err: any) {
      setMsg(err.message);
    } finally {
      setBusy("");
    }
  }

  if (!app) return <div className="card">Loading...</div>;

  const uploadedTypes = new Set(app.documents.map((d: any) => d.doc_type));
  const locked = app.status !== "DRAFT";

  return (
    <div>
      <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0 }}>{app.institution_name}</h2>
          <p className="muted small" style={{ margin: "4px 0 0" }}>{app.category} &middot; AY {app.academic_year} &middot; Status: {app.status}</p>
        </div>
        {app.status !== "DRAFT" && <TierBadge tier={app.risk_tier} />}
      </div>

      <div className="card">
        <h2>Documents</h2>
        {REQUIRED_DOCS.map(docType => {
          const doc = app.documents.find((d: any) => d.doc_type === docType);
          return (
            <div className="doc-row" key={docType}>
              <div>
                <div className="name">{docType.replace(/_/g, " ")}</div>
                <div className="type">{doc ? `${doc.file_name} · ${doc.signature_status}` : "Not uploaded"}</div>
              </div>
              {doc ? <CheckCircle2 size={18} color="#1a8a4a" /> : <span className="muted small">required</span>}
            </div>
          );
        })}
        {!locked && (
          <div style={{ marginTop: 16 }}>
            <label className="btn secondary" style={{ display: "inline-flex", cursor: "pointer" }}>
              <Upload size={16} /> Upload a document
              <input type="file" accept=".pdf,.jpg,.jpeg,.png,.csv" style={{ display: "none" }} onChange={onUpload} />
            </label>
            {busy === "upload" && <span className="muted small" style={{ marginLeft: 10 }}>Uploading &amp; classifying...</span>}
          </div>
        )}
      </div>

      {!locked && (
        <div className="card">
          <h2>Pre-check</h2>
          <p className="muted small">Runs the same validation pipeline the officer sees, and shows a plain-language fix-list.
            Forensic/authenticity indicators are not shown here &mdash; they are for the officer only.</p>
          <button className="btn" onClick={runPrecheck} disabled={busy === "precheck"}>
            <PlayCircle size={16} /> {busy === "precheck" ? "Running..." : "Run pre-check"}
          </button>

          {fixList && (
            <div style={{ marginTop: 18 }}>
              <div style={{ marginBottom: 10 }}>Result: <TierBadge tier={fixList.tier} /> <span className="muted small">score {fixList.score}</span></div>
              {["CRITICAL", "MAJOR", "MINOR"].map(sev => (
                fixList.fix_list[sev]?.length > 0 && (
                  <div key={sev}>
                    <div className="section-title">{sev === "CRITICAL" ? "Must fix" : sev === "MAJOR" ? "Should fix before submitting" : "Minor"}</div>
                    {fixList.fix_list[sev].map((item: any, i: number) => (
                      <div className="flag-item" key={i}>
                        <div className="message">{item.message}</div>
                        <div className="explain">{item.explanation}</div>
                        {item.citation && <div className="citation">{item.citation}</div>}
                      </div>
                    ))}
                  </div>
                )
              ))}
              {Object.values(fixList.fix_list).every((v: any) => v.length === 0) && (
                <p style={{ color: "#1a8a4a" }}><FileText size={14} /> Nothing needs action from your side.</p>
              )}
            </div>
          )}

          <div style={{ marginTop: 18, borderTop: "1px solid var(--border)", paddingTop: 16 }}>
            {!confirmingSubmit ? (
              <button className="btn" onClick={() => setConfirmingSubmit(true)}>
                <Send size={16} /> Submit application
              </button>
            ) : (
              <div className="flag-item" style={{ borderColor: "var(--amber)" }}>
                <div className="message">Submitting locks editing (Clause 2.3.3, p.14).</div>
                <div className="explain">The Regulation Bureau can reopen it only once after this. Are you sure every document is final?</div>
                <div className="actions" style={{ marginTop: 10 }}>
                  <button className="btn" onClick={submit} disabled={busy === "submit"}>
                    {busy === "submit" ? "Submitting..." : "Yes, submit"}
                  </button>
                  <button className="btn secondary" onClick={() => setConfirmingSubmit(false)}>Cancel</button>
                </div>
              </div>
            )}
            {msg && <span className="muted small" style={{ marginLeft: 10 }}>{msg}</span>}
          </div>
        </div>
      )}
    </div>
  );
}
