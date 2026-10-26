import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useNavigate } from "react-router-dom";
import { J } from "../../api";
import { useApi } from "../../hooks";
import { ErrorBox, fmtDate, KPI, Loading, RiskChip, TIER } from "../../ui";

const COLORS: Record<string, string> = { GREEN: "#2E7D5B", AMBER: "#F2A93B", RED: "#C0392B" };

export default function Queue() {
  const [tier, setTier] = useState("");
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const [drafts, setDrafts] = useState(false);
  const qs = new URLSearchParams({ ...(tier && { tier }), ...(category && { category }), ...(q && { q }), ...(drafts && { include_drafts: "true" }) }).toString();
  const queue = useApi<J[]>(`/risk/queue${qs ? "?" + qs : ""}`);
  const stats = useApi<J>("/risk/stats");
  const nav = useNavigate();
  const byTier = useMemo(() => ["RED", "AMBER", "GREEN"].map((t) => ({ name: `${t} (${TIER[t].label})`, tier: t, count: stats.data?.by_tier?.[t] ?? 0 })), [stats.data]);
  const byFeature = useMemo(() => Object.entries(stats.data?.flags_by_feature ?? {}).map(([feature, count]) => ({ feature, count })), [stats.data]);
  const s = stats.data;

  return (
    <>
      <h1>Review queue</h1>
      <p className="muted">Sorted by risk, highest first. GREEN = no risk, AMBER = medium risk, RED = high risk.</p>
      <div className="kpis">
        <KPI label="Applications" value={s?.total_applications ?? "—"} />
        <KPI label="High risk (RED)" value={s?.by_tier?.RED ?? "—"} cls="red" />
        <KPI label="Medium risk (AMBER)" value={s?.by_tier?.AMBER ?? "—"} cls="amber" />
        <KPI label="No risk (GREEN)" value={s?.by_tier?.GREEN ?? "—"} cls="green" />
        <KPI label="Findings (excl. notices)" value={Object.values(s?.flags_by_severity ?? {}).reduce((a: number, b: unknown) => a + (b as number), 0)} />
      </div>
      <div className="grid2">
        <figure className="card chart" aria-label="Applications by risk tier">
          <figcaption>Applications by risk tier</figcaption>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={byTier}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" fontSize={12} /><YAxis allowDecimals={false} /><Tooltip />
              <Bar dataKey="count" name="Applications">{byTier.map((d) => <Cell key={d.tier} fill={COLORS[d.tier]} />)}</Bar></BarChart>
          </ResponsiveContainer>
        </figure>
        <figure className="card chart" aria-label="Findings by feature">
          <figcaption>Findings by feature</figcaption>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={byFeature}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="feature" fontSize={12} /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="count" name="Findings" fill="#1F3864" /></BarChart>
          </ResponsiveContainer>
        </figure>
      </div>
      <div className="card">
        <div className="row gap end filters">
          <label>Risk<select value={tier} onChange={(e) => setTier(e.target.value)}><option value="">All</option>{Object.entries(TIER).map(([k, v]) => <option key={k} value={k}>{k} · {v.label}</option>)}</select></label>
          <label>Category<select value={category} onChange={(e) => setCategory(e.target.value)}><option value="">All</option><option value="EOA">EoA</option><option value="INCREASE_IN_INTAKE">Increase in intake</option><option value="NAME_CHANGE_INSTITUTION">Name change</option></select></label>
          <label>Institution<input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name" /></label>
          <label className="check"><input type="checkbox" checked={drafts} onChange={(e) => setDrafts(e.target.checked)} /> Include drafts</label>
        </div>
        {queue.loading && <Loading />}<ErrorBox message={queue.error} />
        <table className="clickable">
          <thead><tr><th>Institution</th><th>Category</th><th>Risk</th><th>Top reason</th><th>Open findings</th><th>Submitted</th></tr></thead>
          <tbody>
            {(queue.data ?? []).map((i) => (
              <tr key={i.application_id} tabIndex={0} onClick={() => nav(`/officer/applications/${i.application_id}`)} onKeyDown={(e) => e.key === "Enter" && nav(`/officer/applications/${i.application_id}`)}>
                <td><strong>{i.institution_name}</strong><div className="muted">{i.state} · AY {i.academic_year}</div></td>
                <td>{i.category.replaceAll("_", " ")}</td>
                <td><RiskChip tier={i.tier} score={i.score} /></td>
                <td>{i.top_reason ?? <span className="muted">No findings</span>}</td>
                <td>{i.open_flags}</td>
                <td>{fmtDate(i.submitted_at)}{i.status === "DRAFT" && <span className="chip blue">Draft</span>}</td>
              </tr>
            ))}
            {queue.data?.length === 0 && <tr><td colSpan={6} className="muted">No applications match.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
