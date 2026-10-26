import { useEffect, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { blobUrl, J } from "../api";

pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

export type Target = { document_id: number; page?: number | null; bbox?: number[] | null; field?: string | null };
const WIDTH = 520;

function useBlob(path: string | null) {
  const [url, setUrl] = useState<string>("");
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!path) return;
    let live = true, made = "";
    setUrl(""); setErr("");
    blobUrl(path).then((u) => { made = u; if (live) setUrl(u); }).catch((e) => live && setErr(e.message));
    return () => { live = false; if (made) URL.revokeObjectURL(made); };
  }, [path]);
  return { url, err };
}

function Box({ bbox, label }: { bbox?: number[] | null; label?: string | null }) {
  if (!bbox) return null;
  const [x0, y0, x1, y1] = bbox;
  return <div className="bbox" style={{ left: `${x0 * 100 - 0.6}%`, top: `${y0 * 100 - 0.4}%`, width: `${(x1 - x0) * 100 + 1.2}%`, height: `${(y1 - y0) * 100 + 0.8}%` }} title={label ?? ""}><span>{label}</span></div>;
}

/** Shows the cited document page with the evidence bounding box highlighted. Photos render as images; ELA toggles the error-level heatmap. */
export default function EvidenceViewer({ target, doc, compare }: { target: Target; doc?: J; compare?: { doc?: J; target: Target } | null }) {
  const [ela, setEla] = useState(false);
  useEffect(() => setEla(false), [target.document_id]);
  const isImage = doc?.content_type?.startsWith("image/");
  const isData = !isImage && (doc?.content_type === "text/csv" || /\.csv$/i.test(doc?.filename ?? ""));
  const file = useBlob(isImage || isData || ela ? null : `/documents/${target.document_id}/file`);
  const heat = useBlob(ela ? `/documents/${target.document_id}/forensics/ela.png` : null);
  const img = useBlob(isImage ? `/documents/${target.document_id}/pages/1.png` : null);
  const other = useBlob(compare ? `/documents/${compare.target.document_id}/pages/1.png` : null);
  const [pages, setPages] = useState(1);
  const page = target.page ?? 1;

  return (
    <div className="viewer" aria-label="Evidence viewer">
      <div className="viewer-bar">
        <strong>{doc ? doc.doc_type.replaceAll("_", " ") : `Document ${target.document_id}`}</strong>
        <span className="muted">{doc?.filename} · page {page}{target.field ? ` · ${target.field}` : ""}</span>
        <span className="spacer" />
        {doc?.has_ela && <button onClick={() => setEla(!ela)} aria-pressed={ela}>{ela ? "Show document" : "Show ELA heatmap"}</button>}
      </div>
      {ela && <p className="muted small">Error Level Analysis: bright areas recompress differently. A preliminary indicator only; crisp text is bright everywhere.</p>}
      <div className={compare ? "side-by-side" : ""}>
        <div className="page-wrap" style={{ width: WIDTH }}>
          {ela && heat.url && <img src={heat.url} alt="ELA heatmap" width={WIDTH} />}
          {!ela && isImage && img.url && <img src={img.url} alt={`Photo ${doc?.filename}`} width={WIDTH} />}
          {!ela && isData && <p className="muted pad">This is a data file (CSV), so it has no page preview. The figures it contributes are explained in the flag details beside it.</p>}
          {!ela && !isImage && !isData && file.url && (
            <Document file={file.url} onLoadSuccess={(p) => setPages(p.numPages)} loading={<p className="muted pad">Rendering…</p>} error={<p className="err pad">Could not render the PDF.</p>}>
              <Page pageNumber={Math.min(page, pages)} width={WIDTH} renderTextLayer={false} renderAnnotationLayer={false} />
            </Document>
          )}
          {(file.err || img.err || heat.err) && <p className="err pad">{file.err || img.err || heat.err}</p>}
          <Box bbox={target.bbox} label={target.field} />
        </div>
        {compare && <div className="page-wrap" style={{ width: WIDTH }}><div className="cap">Same photo from another institution</div>{other.url && <img src={other.url} alt="Matching photo from another institution" width={WIDTH} />}</div>}
      </div>
    </div>
  );
}
