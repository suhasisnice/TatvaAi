import { useState } from "react";
import { J } from "../../api";
import { useApi } from "../../hooks";
import EvidenceViewer from "../EvidenceViewer";
import { Loading } from "../../ui";

export default function Timeline({ appId, docs }: { appId: number; docs: J[] }) {
  const tl = useApi<J>(`/applications/${appId}/timeline`);
  const [open, setOpen] = useState<J>(null);
  if (tl.loading && !tl.data) return <Loading />;
  const events: J[] = tl.data?.events ?? [];
  return (
    <div className="split">
      <section className="card left">
        <h2>Document timeline</h2>
        <p className="muted">Dates read from each document, in order. Impossible sequences are marked in red.</p>
        {tl.data?.impossible?.map((i: J) => <p key={i.flag_id} role="alert" className="err">Impossible sequence: {i.message}</p>)}
        <ol className="timeline">
          {events.map((e, i) => (
            <li key={i} className={`${e.impossible ? "bad" : ""} ${e.marker ? "marker" : ""}`}>
              <time dateTime={e.date}>{e.date}</time>
              {e.document_id ? <button className="linkish" onClick={() => setOpen(e)}>{e.label}</button> : <span>{e.label}</span>}
              {e.impossible && <span className="chip red">Impossible sequence</span>}
              <span className="muted small">{e.document_type?.replaceAll("_", " ")}</span>
            </li>
          ))}
        </ol>
      </section>
      <div className="right">
        {open ? <EvidenceViewer key={`${open.document_id}-${open.field}`} target={{ document_id: open.document_id, page: open.page, bbox: open.bbox, field: open.field }} doc={docs.find((d) => d.id === open.document_id)} />
          : <p className="card muted">Select a dated event to see where it appears in the document.</p>}
      </div>
    </div>
  );
}
