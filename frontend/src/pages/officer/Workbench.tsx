import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { RefreshCw, Unlock, FileDown } from "lucide-react";
import { api } from "../../lib/api";
import { TierBadge, SevBadge } from "../../components/Badges";

export default function Workbench() {
  const { id } = useParams();
  const [app, setApp] = useState<any>(null);
  const [tab, setTab] = useState<"summary" | "flags" | "verification" | "documents">("summary");
  const [reasons, setReasons] = useState<Record<number, string>>({});
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);

  function load() {
    api.getApplication(Number(id)).then(setApp);
  }
  useEffect(load, [id]);

  async function revalidate() {
    setBusy(true);
    try { await api.revalidate(Number(id)); load(); } finally { setBusy(false); }
  }

  async function reopen() {
    setBusy(true);
    try { await api.reopen(Number(id)); load(); }
    catch (err: any) { alert(err.message); }
    finally { setBusy(false); }
  }

  async function decide(flagId: number, decision: "ACCEPT" | "DISMISS") {
    const reason = reasons[flagId];
    if (!reason || reason.trim().length < 5) { alert("Reason must be at least 5 characters."); return; }
    await api.decideFlag(flagId, decision, reason);
    load();
  }

  async function manualVerify(vId: number) {
    const note = notes[vId];
    if (!note || note.trim().length < 5) { alert("Note must be at least 5 characters."); return; }
    await api.manualVerify(vId, note);
    load();
  }

  if (!app) return <div className="card">Loading...</div>;

  return (
    <div>
      <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0 }}>{app.institution_name}</h2>
          <p className="muted small" style={{ margin: "4px 0 0" }}>{app.state} &middot; {app.aicte_id} &middot; {app.category} &middot; AY {app.academic_year} &middot; {app.status}</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <TierBadge tier={app.risk_tier} />
          <span className="muted small">score {app.risk_score}</span>
          <button className="btn secondary" onClick={revalidate} disabled={busy}>
            <RefreshCw size={14} /> Re-run validation
          </button>
          <button className="btn secondary" onClick={() => api.downloadReport(Number(id)).catch((e: any) => alert(e.message))}>
            <FileDown size={14} /> Validation report
          </button>
          {app.status === "SUBMITTED" && app.reopen_count < 1 && (
            <button className="btn secondary" onClick={reopen} disabled={busy} title="Allowed once (Clause 2.3.3, p.14)">
              <Unlock size={14} /> Reopen once
            </button>
          )}
        </div>
      </div>

      <div className="pill-tabs">
        <button className={tab === "summary" ? "active" : ""} onClick={() => setTab("summary")}>Summary</button>
        <button className={tab === "flags" ? "active" : ""} onClick={() => setTab("flags")}>Flags &amp; Evidence</button>
        <button className={tab === "verification" ? "active" : ""} onClick={() => setTab("verification")}>Verification</button>
        <button className={tab === "documents" ? "active" : ""} onClick={() => setTab("documents")}>Documents</button>
      </div>

      {tab === "summary" && (
        <div className="card">
          <h2>Top reasons</h2>
          {(app.top_reasons || []).length === 0 && <p className="muted">No findings need attention.</p>}
          <ul>{app.top_reasons.map((r: string, i: number) => <li key={i}>{r}</li>)}</ul>
        </div>
      )}

      {tab === "flags" && (
        <div className="card">
          <h2>Flags &amp; evidence ({app.flags.length})</h2>
          {app.flags.map((f: any) => (
            <div className={`flag-item ${f.status === "DISMISSED" ? "dismissed" : ""}`} key={f.id}>
              <div className="top">
                <SevBadge severity={f.severity} />
                <span className="small muted">{f.engine}</span>
                <span className="small muted">{f.code}</span>
                {f.forensic && <span className="small" style={{ color: "#b4720a" }}>preliminary indicator &middot; conf {f.confidence}</span>}
                <span className="small" style={{ marginLeft: "auto" }}>{f.status}</span>
              </div>
              <div className="message">{f.message}</div>
              <div className="explain">{f.explanation}</div>
              {f.citation && <div className="citation">{f.citation}</div>}
              {f.status === "OPEN" && (
                <div className="actions">
                  <input placeholder="Reason (required)" value={reasons[f.id] || ""}
                         onChange={e => setReasons({ ...reasons, [f.id]: e.target.value })} />
                  <button className="btn secondary" onClick={() => decide(f.id, "ACCEPT")}>Accept</button>
                  <button className="btn danger" onClick={() => decide(f.id, "DISMISS")}>Dismiss</button>
                </div>
              )}
              {f.status !== "OPEN" && f.decision_reason && (
                <div className="small muted" style={{ marginTop: 6 }}>Reason: {f.decision_reason}</div>
              )}
            </div>
          ))}
          {app.flags.length === 0 && <p className="muted">No findings.</p>}
        </div>
      )}

      {tab === "verification" && (
        <div className="card">
          <h2>Issuer verification</h2>
          <table>
            <thead><tr><th>Source</th><th>Status</th><th>Summary</th><th></th></tr></thead>
            <tbody>
              {app.verifications.map((v: any) => (
                <tr key={v.id}>
                  <td>{v.source_name}</td>
                  <td><SevBadge severity={v.status === "VERIFIED" ? "MINOR" : v.status === "MISMATCH_DETECTED" ? "CRITICAL" : "MAJOR"} /> {v.status}</td>
                  <td className="small muted">{v.manual_note ? `Manually confirmed: ${v.manual_note}` : v.summary}</td>
                  <td>
                    {v.status === "MANUAL_REVIEW_REQUIRED" && (
                      <div style={{ display: "flex", gap: 6 }}>
                        <input placeholder="Confirmation note" value={notes[v.id] || ""}
                               onChange={e => setNotes({ ...notes, [v.id]: e.target.value })} style={{ width: 160 }} />
                        <button className="btn secondary" onClick={() => manualVerify(v.id)}>Confirm</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {app.verifications.length === 0 && <tr><td colSpan={4} className="muted">No issuer checks recorded.</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {tab === "documents" && (
        <div className="card">
          <h2>Documents</h2>
          {app.documents.map((d: any) => (
            <div className="doc-row" key={d.id}>
              <div>
                <div className="name">{d.doc_type.replace(/_/g, " ")}</div>
                <div className="type">{d.file_name} &middot; sha256 {d.sha256}&hellip; &middot; classified {Math.round(d.classification_confidence * 100)}% confident</div>
              </div>
              <SevBadge severity={["SIGNED_VALID", "NOT_APPLICABLE"].includes(d.signature_status) ? "MINOR" : ["SIGNED_MODIFIED", "SIGNED_INVALID"].includes(d.signature_status) ? "CRITICAL" : "MAJOR"} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
