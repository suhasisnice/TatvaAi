import { useEffect, useState } from "react";
import { FileText, ShieldAlert, CheckCircle2, XCircle } from "lucide-react";
import { api } from "../../lib/api";
import { SevBadge } from "../../components/Badges";

type ChecklistItem = {
  flag_id: number;
  code: string;
  severity: string;
  message: string;
  instruction: string;
  inspection_status: "PENDING" | "CONFIRMED" | "CLEARED";
  inspection_note: string | null;
  inspection_by: string | null;
};

type DocGroup = {
  document_id: number | null;
  document_type: string;
  file_name: string | null;
  items: ChecklistItem[];
};

type AppEntry = {
  application_id: number;
  institution_name: string;
  score: number;
  top_reasons: string[];
  document_groups: DocGroup[];
  progress: { resolved: number; total: number };
};

export default function InspectionList() {
  const [rows, setRows] = useState<AppEntry[]>([]);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);

  function load() {
    api.inspectionList().then(r => { setRows(r); setLoading(false); });
  }
  useEffect(load, []);

  async function decide(flagId: number, status: "CONFIRMED" | "CLEARED") {
    const note = notes[flagId];
    if (!note || note.trim().length < 5) { alert("Add a short on-site note (at least 5 characters) first."); return; }
    await api.decideInspection(flagId, status, note);
    load();
  }

  if (loading) return <div className="card">Loading...</div>;

  return (
    <div>
      <div className="card">
        <h2>Risk-targeted inspection list</h2>
        <p className="muted small">RED applications, ranked by score, grouped by the document each finding came
          from, with an on-site checklist &mdash; this replaces random EVC selection (Clause 2.3.5 (a), p.15).
          Mark each item <strong>Confirmed</strong> if your on-site check agrees there's an issue, or
          <strong> Cleared</strong> if it turns out to be a false alarm; both need a note.</p>
      </div>

      {rows.map(r => {
        const pct = r.progress.total ? Math.round((r.progress.resolved / r.progress.total) * 100) : 0;
        return (
          <div className="card" key={r.application_id}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
              <h2 style={{ margin: 0 }}>{r.institution_name}</h2>
              <span className="muted small">score {r.score}</span>
            </div>

            <div className="progress-wrap" style={{ margin: "10px 0 16px" }}>
              <div className="progress-bar"><div className="fill" style={{ width: `${pct}%` }} /></div>
              <span className="progress-label">{r.progress.resolved} / {r.progress.total} items resolved</span>
            </div>

            <div className="section-title">Why this institution</div>
            <ul className="small">{r.top_reasons.map((reason, i) => <li key={i}>{reason}</li>)}</ul>

            <div className="section-title">On-site checklist, by document</div>
            {r.document_groups.map(g => (
              <div className="doc-group" key={g.document_id ?? "institution"}>
                <div className="doc-group-header">
                  <span className="title"><FileText size={13} style={{ verticalAlign: -2, marginRight: 5 }} />{g.document_type}</span>
                  {g.file_name && <span className="file">{g.file_name}</span>}
                </div>
                {g.items.map(item => (
                  <div className={`check-card ${item.inspection_status !== "PENDING" ? "resolved" : ""}`} key={item.flag_id}>
                    <div className="top">
                      <SevBadge severity={item.severity} />
                      <code style={{ background: "var(--blue-light)", padding: "1px 6px", borderRadius: 4, fontSize: 11, color: "var(--navy)" }}>{item.code}</code>
                      <span className={`status-dot ${item.inspection_status}`}>
                        {item.inspection_status === "PENDING" && <ShieldAlert size={11} />}
                        {item.inspection_status === "CONFIRMED" && <XCircle size={11} />}
                        {item.inspection_status === "CLEARED" && <CheckCircle2 size={11} />}
                        {item.inspection_status}
                      </span>
                    </div>
                    <div className="instruction">{item.instruction}</div>
                    <div className="finding">System finding: {item.message}</div>

                    {item.inspection_status === "PENDING" ? (
                      <div className="insp-actions">
                        <input placeholder="On-site note (required)" value={notes[item.flag_id] || ""}
                               onChange={e => setNotes({ ...notes, [item.flag_id]: e.target.value })} />
                        <button className="btn danger" onClick={() => decide(item.flag_id, "CONFIRMED")}>Confirm issue</button>
                        <button className="btn secondary" onClick={() => decide(item.flag_id, "CLEARED")}>Clear</button>
                      </div>
                    ) : (
                      <div className={`result ${item.inspection_status}`}>
                        {item.inspection_by}: {item.inspection_note}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>
        );
      })}
      {rows.length === 0 && <div className="card muted">No high-risk applications currently need inspection.</div>}
    </div>
  );
}
