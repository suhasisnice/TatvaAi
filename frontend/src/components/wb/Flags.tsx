import { useEffect, useMemo, useState } from "react";
import { J, post } from "../../api";
import { useApi } from "../../hooks";
import EvidenceViewer from "../EvidenceViewer";
import { cite, ErrorBox, FEATURES, fmtDate, Loading, MockTag, Prelim, SeverityChip } from "../../ui";

const ORDER: Record<string, number> = { CRITICAL: 0, MAJOR: 1, MINOR: 2, INFO: 3 };

export default function Flags({ appId, docs, canDecide, onChanged, focusFlagId }: { appId: number; docs: J[]; canDecide: boolean; onChanged: () => void; focusFlagId?: number }) {
  const flags = useApi<J[]>(`/flags?application_id=${appId}`);
  const [feature, setFeature] = useState("");
  const [showInfo, setShowInfo] = useState(false);
  const [showDismissed, setShowDismissed] = useState(true);
  const [sel, setSel] = useState<number | null>(null);
  const [evIdx, setEvIdx] = useState(0);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  const docMap = useMemo(() => Object.fromEntries(docs.map((d) => [d.id, d])), [docs]);
  const list = useMemo(() => (flags.data ?? []).filter((f) => (!feature || String(f.feature) === feature) && (showInfo || f.severity !== "INFO") && (showDismissed || f.status !== "DISMISSED"))
    .sort((a, b) => ORDER[a.severity] - ORDER[b.severity] || a.id - b.id), [flags.data, feature, showInfo, showDismissed]);
  useEffect(() => { if (focusFlagId) setSel(focusFlagId); }, [focusFlagId]);
  useEffect(() => { if (sel == null && list.length) setSel(list[0].id); }, [list, sel]);
  const flag = (flags.data ?? []).find((f) => f.id === sel);
  useEffect(() => { setEvIdx(0); setReason(""); setErr(""); }, [sel]);

  if (flags.loading && !flags.data) return <Loading />;
  const ev: J[] = flag?.evidence ?? [];
  const docEv = ev.filter((e) => e.document_id && !e.other_institution);
  const current = docEv[Math.min(evIdx, docEv.length - 1)];
  const other = ev.find((e) => e.other_institution);

  const decide = async (decision: "ACCEPT" | "DISMISS") => {
    setErr("");
    try { await post(`/flags/${flag.id}/decision`, { decision, reason }); setReason(""); flags.reload(); onChanged(); } catch (e) { setErr((e as Error).message); }
  };

  return (
    <div className="split">
      <div className="left">
        <div className="row gap end filters">
          <label>Feature<select value={feature} onChange={(e) => setFeature(e.target.value)}><option value="">All findings</option>{[1, 2].map((n) => <option key={n} value={n}>{FEATURES[n]}</option>)}</select></label>
          <label className="check"><input type="checkbox" checked={showInfo} onChange={(e) => setShowInfo(e.target.checked)} /> Notices (INFO)</label>
          <label className="check"><input type="checkbox" checked={showDismissed} onChange={(e) => setShowDismissed(e.target.checked)} /> Dismissed</label>
        </div>
        <ul className="flaglist" role="listbox" aria-label="Flags">
          {list.map((f) => (
            <li key={f.id}>
              <button role="option" aria-selected={f.id === sel} className={`flagitem ${f.id === sel ? "on" : ""} ${f.status === "DISMISSED" ? "dim" : ""}`} onClick={() => setSel(f.id)}>
                <span className="row gap"><SeverityChip severity={f.severity} /><code>{f.code}</code>{f.status !== "OPEN" && <span className="chip grey">{f.status}</span>}</span>
                <span>{f.message}</span>
              </button>
            </li>
          ))}
          {list.length === 0 && <li className="muted pad">No flags match.</li>}
        </ul>
        {flag && (
          <article className="card flagdetail" aria-label="Flag detail">
            <h3><code>{flag.code}</code> <SeverityChip severity={flag.severity} /> <span className="chip grey" title={`engine: ${flag.engine}`}>{FEATURES[flag.feature]}</span></h3>
            {flag.preliminary_indicator && <p><Prelim /></p>}
            <p>{flag.message}</p>
            {flag.explanation && <p className="muted">{flag.explanation}</p>}
            {flag.citation && <p><b>Citation:</b> {cite(flag.citation)} · rule {flag.rule_id} · pack {flag.rule_pack_version}</p>}
            <p className="muted">Confidence {Math.round(flag.confidence * 100)}%</p>
            <h4>Evidence</h4>
            <ul className="plain">
              {ev.map((e, i) => {
                const di = docEv.indexOf(e);
                return (
                  <li key={i}>
                    {e.document_id && !e.other_institution ? <button className={`linkish ${di === evIdx ? "on" : ""}`} onClick={() => setEvIdx(di)}>
                      {docMap[e.document_id]?.doc_type.replaceAll("_", " ") ?? `Document ${e.document_id}`} · p.{e.page ?? 1}{e.field ? ` · ${e.field}` : ""}{e.value ? ` = ${String(e.value).slice(0, 40)}` : ""}
                    </button> : e.system_source ? <span>{e.system_source}{e.mock && <> <MockTag /></>} · {e.record_id}</span> : <span>Photo from another institution{e.distance != null ? ` (distance ${e.distance}/64)` : ""}</span>}
                  </li>
                );
              })}
            </ul>
            <h4>Officer decision</h4>
            {flag.decisions.map((d: J, i: number) => <p key={i} className="decision">{d.decision === "ACCEPT" ? "Accepted" : "Dismissed"} on {fmtDate(d.decided_at)}: “{d.reason}”</p>)}
            {canDecide ? (
              <>
                <label>Reason (required)<textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} placeholder="Why is this finding valid / not valid?" /></label>
                <div className="row gap">
                  <button className="primary" disabled={reason.trim().length < 5} onClick={() => decide("ACCEPT")}>Accept finding</button>
                  <button disabled={reason.trim().length < 5} onClick={() => decide("DISMISS")}>Dismiss with reason</button>
                </div>
                <p className="muted small">Dismissing keeps the flag on record and updates the score. There is no “reject application” action.</p>
              </>
            ) : <p className="muted">Only scrutiny officers record decisions.</p>}
            <ErrorBox message={err} />
          </article>
        )}
      </div>
      <div className="right">
        {current ? <EvidenceViewer key={`${current.document_id}-${flag?.id}`} target={current} doc={docMap[current.document_id]}
          compare={flag?.code === "DUPLICATE_PHOTO" && other ? { doc: docMap[other.document_id], target: other } : null} />
          : <p className="card muted">This flag is based on a system record, not a document page. See the evidence list.</p>}
      </div>
    </div>
  );
}
