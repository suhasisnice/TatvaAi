import { FileDown } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { download, J, post } from "../../api";
import { useApi } from "../../hooks";
import { ErrorBox, Loading, RiskChip, SeverityChip } from "../../ui";

/** One on-site checklist item. Inspectors record a verdict; officers see it read-only. */
function Item({ item, canDecide, onDone }: { item: J; canDecide: boolean; onDone: () => void }) {
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const decide = (status: "CONFIRMED" | "CLEARED") =>
    post(`/flags/${item.flag_id}/inspection`, { status, note }).then(onDone).catch((e) => setErr(e.message));
  const pending = item.inspection_status === "PENDING";
  return (
    <li className={`check-item ${pending ? "" : "done"}`}>
      <div className="row"><SeverityChip severity={item.severity} /> <code>{item.code}</code> <span className={`verdict ${item.inspection_status}`}>{item.inspection_status}</span></div>
      <p className="check-text">{item.check}</p>
      <p className="muted small">System finding: {item.finding}</p>
      {pending && canDecide && (
        <div className="row">
          <input aria-label="On-site note" placeholder="On-site note (required)" value={note} onChange={(e) => setNote(e.target.value)} />
          <button className="danger" disabled={note.trim().length < 5} onClick={() => decide("CONFIRMED")}>Confirm issue</button>
          <button disabled={note.trim().length < 5} onClick={() => decide("CLEARED")}>Clear</button>
        </div>
      )}
      {!pending && <p className={`verdict-note ${item.inspection_status}`}>{item.inspection_by}: {item.inspection_note}</p>}
      <ErrorBox message={err} />
    </li>
  );
}

export default function Inspections({ canDecide = false }: { canDecide?: boolean }) {
  const { data, loading, error, reload } = useApi<J[]>("/risk/inspection-list");
  const [err, setErr] = useState("");
  return (
    <>
      <div className="row between">
        <div><h1>Risk-targeted inspection list</h1><p className="muted">RED = high risk applications, ranked by score and grouped by the document each finding came from. This replaces random selection for inspection (APH clause 2.3.5).{canDecide ? " Mark each item Confirmed if your on-site check agrees there is an issue, or Cleared if it is a false alarm; both need a note." : ""}</p></div>
        <button className="primary" onClick={() => download("/risk/inspection-list.pdf", "inspection-list.pdf").catch((e) => setErr(e.message))}><FileDown size={16} aria-hidden /> Export checklist PDF</button>
      </div>
      <ErrorBox message={err || error} />{loading && <Loading />}
      {data?.length === 0 && <p className="card muted">No RED applications at this time.</p>}
      {(data ?? []).map((i) => {
        const pct = i.progress.total ? Math.round((i.progress.resolved / i.progress.total) * 100) : 0;
        return (
          <article key={i.application_id} className="card inspection">
            <div className="row between">
              <h2>#{i.rank} {i.institution_name}</h2>
              <RiskChip tier={i.tier} score={i.score} />
            </div>
            <p className="muted">{i.state} · {i.category.replaceAll("_", " ")} · AY {i.academic_year} · rule pack {i.rule_pack_version}</p>
            <div className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><div style={{ width: `${pct}%` }} /></div>
            <p className="muted small">{i.progress.resolved} / {i.progress.total} items resolved</p>
            <h3>Why this institution</h3>
            <ul className="plain">{i.reasons.map((r: J) => <li key={r.flag_id}><SeverityChip severity={r.severity} /> {r.message}</li>)}</ul>
            <h3>On-site checklist, by document</h3>
            {i.document_groups.map((g: J) => (
              <section key={g.document_id ?? "institution"} className="doc-group">
                <header><strong>{g.document_type}</strong>{g.filename && <span className="muted small">{g.filename}</span>}</header>
                <ul className="plain">{g.items.map((it: J) => <Item key={it.flag_id} item={it} canDecide={canDecide} onDone={reload} />)}</ul>
              </section>
            ))}
            <Link to={`/officer/applications/${i.application_id}`}>Open evidence workbench</Link>
          </article>
        );
      })}
    </>
  );
}
