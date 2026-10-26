import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { TierBadge } from "../../components/Badges";

export default function Queue() {
  const [data, setData] = useState<any>(null);
  const navigate = useNavigate();

  useEffect(() => { api.queue().then(setData); }, []);

  if (!data) return <div className="card">Loading...</div>;

  return (
    <div>
      <div className="grid cols-4">
        <div className="card kpi"><div className="num">{data.kpi.total}</div><div className="label">Applications</div></div>
        <div className="card kpi"><div className="num" style={{ color: "#c4293a" }}>{data.kpi.red}</div><div className="label">Red</div></div>
        <div className="card kpi"><div className="num" style={{ color: "#b4720a" }}>{data.kpi.amber}</div><div className="label">Amber</div></div>
        <div className="card kpi"><div className="num" style={{ color: "#1a8a4a" }}>{data.kpi.green}</div><div className="label">Green</div></div>
      </div>

      <div className="card">
        <h2>Review queue</h2>
        <table>
          <thead>
            <tr><th>Institution</th><th>Category</th><th>AY</th><th>Risk</th><th>Top reason</th><th>Open findings</th></tr>
          </thead>
          <tbody>
            {data.rows.map((r: any) => (
              <tr key={r.id} className="clickable" onClick={() => navigate(`/officer/applications/${r.id}`)}>
                <td>{r.institution_name}</td>
                <td>{r.category}</td>
                <td>{r.academic_year}</td>
                <td><TierBadge tier={r.risk_tier} /></td>
                <td className="small muted">{r.top_reason}</td>
                <td>{r.open_flags}</td>
              </tr>
            ))}
            {data.rows.length === 0 && <tr><td colSpan={6} className="muted">No submitted applications yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
