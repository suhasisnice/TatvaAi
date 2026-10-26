import { useEffect, useState } from "react";
import { blobUrl } from "../api";

/** <img> for an authenticated API path (fetched as a blob because <img src> cannot send the bearer token). */
export default function Img({ path, alt, width }: { path: string; alt: string; width?: number }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let live = true, made = "";
    blobUrl(path).then((u) => { made = u; if (live) setUrl(u); }).catch(() => undefined);
    return () => { live = false; if (made) URL.revokeObjectURL(made); };
  }, [path]);
  return url ? <img src={url} alt={alt} width={width} /> : <div className="img-ph" style={{ width }} aria-label={`Loading ${alt}`} />;
}
