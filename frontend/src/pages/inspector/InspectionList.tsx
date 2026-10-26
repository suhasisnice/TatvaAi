import { useEffect, useState } from "react";
import { api } from "../../lib/api";

export default function InspectionList() {
  const [rows, setRows] = useState<any[]>([]);

  useEffect(() => { api.inspectionList().then(setRows); }, []);

  return (
    <div>
      <div className="card">
        <h2>Risk-targeted inspection list</h2>
        <p className="muted small">RED applications, ranked by score, with the reasons and an on-site checklist &mdash;
          replacing random selection (Clause 2.3.5 (a), p.15).</p>
      </div>

      {rows.map(r => (
        <div className="card" key={r.application_id}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <h2 style={{ margin: 0 }}>{r.institution_name}</h2>
            <span className="muted small">score {r.score}</span>
          </div>
          <div className="section-title">Why this institution</div>
          <ul className="small">{r.top_reasons.map((reason: string, i: number) => <li key={i}>{reason}</li>)}</ul>
          <div className="section-title">On-site checklist</div>
          {r.checklist.map((item: any, i: number) => (
            <div className="checklist-item" key={i}>
              <code>{item.code}</code>
              <span>{item.instruction}</span>
            </div>
          ))}
        </div>
      ))}
      {rows.length === 0 && <div className="card muted">No high-risk applications currently need inspection.</div>}
    </div>
  );
}
