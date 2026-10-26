import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FilePlus2 } from "lucide-react";
import { api } from "../../lib/api";
import { TierBadge } from "../../components/Badges";

export default function MyApplications() {
  const [apps, setApps] = useState<any[]>([]);
  const [creating, setCreating] = useState(false);
  const [categories, setCategories] = useState<any[]>([]);
  const [category, setCategory] = useState("EOA");
  const navigate = useNavigate();

  function load() {
    api.listApplications().then(setApps);
  }
  useEffect(load, []);
  useEffect(() => { api.categories().then(setCategories); }, []);

  async function createNew() {
    setCreating(true);
    try {
      const app = await api.createApplication("2027-28", category);
      navigate(`/institution/applications/${app.id}`);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0 }}>My applications</h2>
          <p className="muted small" style={{ margin: "4px 0 0" }}>AY 2027-28</p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <select value={category} onChange={e => setCategory(e.target.value)} style={{ width: 300 }}>
            {categories.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
          <button className="btn" onClick={createNew} disabled={creating}>
            <FilePlus2 size={16} /> Start new application
          </button>
        </div>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr><th>Category</th><th>Academic year</th><th>Status</th><th>Risk</th><th></th></tr>
          </thead>
          <tbody>
            {apps.map(a => (
              <tr key={a.id} className="clickable" onClick={() => navigate(`/institution/applications/${a.id}`)}>
                <td>{a.category_title}</td>
                <td>{a.academic_year}</td>
                <td>{a.status}</td>
                <td>{a.status === "DRAFT" ? <span className="muted small">Not yet checked</span> : <TierBadge tier={a.risk_tier} />}</td>
                <td><button className="btn secondary">Open</button></td>
              </tr>
            ))}
            {apps.length === 0 && <tr><td colSpan={5} className="muted">No applications yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
