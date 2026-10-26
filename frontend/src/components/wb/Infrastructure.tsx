import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect, useState } from "react";
import { Circle, CircleMarker, GeoJSON, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import { J } from "../../api";
import { useApi } from "../../hooks";
import Img from "../Img";
import { Loading, MockTag } from "../../ui";

const TILES = import.meta.env.VITE_TILES_URL as string | undefined; // no external map tiles unless explicitly configured

function Fit({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => { if (points.length) map.fitBounds(L.latLngBounds(points), { padding: [30, 30], maxZoom: 17 }); }, [map, points]);
  return null;
}

export default function Infrastructure({ appId, docs }: { appId: number; docs: J[] }) {
  const infra = useApi<J>(`/applications/${appId}/infrastructure`);
  const [scope, setScope] = useState<"campus" | "all">("campus");
  const d = infra.data;
  if (infra.loading && !d) return <Loading />;
  if (!d?.campus) return <p className="card muted">No campus data.</p>;
  const campus: [number, number] = [d.campus.lat, d.campus.lon];
  const photos = d.photos.filter((p: J) => p.lat != null);
  const pts: [number, number][] = scope === "all" ? [campus, ...photos.map((p: J) => [p.lat, p.lon] as [number, number])] : [campus, ...photos.filter((p: J) => !p.offsite).map((p: J) => [p.lat, p.lon] as [number, number])];
  const feats: J[] = d.footprints?.features ?? [];
  const expected = feats.reduce((s, f) => s + f.properties.area_m2 * f.properties.floors, 0);
  const dev = expected && d.declared_built_up_total_m2 ? Math.abs(d.declared_built_up_total_m2 - expected) / expected : null;
  const dupOf = (id: number) => d.duplicates.find((x: J) => x.photo_document_id === id);

  return (
    <>
      <section className="card">
        <div className="row between">
          <h2>Campus map</h2>
          <div className="row gap">
            <button aria-pressed={scope === "campus"} onClick={() => setScope("campus")}>Zoom to campus</button>
            <button aria-pressed={scope === "all"} onClick={() => setScope("all")}>Show all photo locations</button>
          </div>
        </div>
        <p className="muted small">Blue = declared campus (main entrance) with the {d.radius_km} km allowed radius. Green photo = on site, red = off-site GPS. Building footprints from {d.footprint_source} <MockTag />. {TILES ? "" : "Base map tiles are disabled (no external calls); set VITE_TILES_URL to enable."}</p>
        <MapContainer center={campus} zoom={15} className="map" scrollWheelZoom={false}>
          {TILES && <TileLayer url={TILES} attribution="Tiles: configured provider" />}
          <Fit points={pts} />
          <Circle center={campus} radius={d.radius_km * 1000} pathOptions={{ color: "#1F3864", weight: 1, fillOpacity: 0.04 }} />
          <CircleMarker center={campus} radius={8} pathOptions={{ color: "#1F3864", fillColor: "#1F3864", fillOpacity: 1 }}><Popup>Declared campus point (main entrance)</Popup></CircleMarker>
          {d.footprints && <GeoJSON key={appId} data={d.footprints} style={{ color: "#555", weight: 2, fillColor: "#8aa", fillOpacity: 0.5 }} onEachFeature={(f, l) => l.bindPopup(`${f.properties.building}: ${f.properties.area_m2} sq m × ${f.properties.floors} floors, first seen in imagery ${f.properties.first_seen_year}`)} />}
          {photos.map((p: J) => (
            <CircleMarker key={p.document_id} center={[p.lat, p.lon]} radius={8} pathOptions={{ color: p.offsite ? "#C0392B" : "#2E7D5B", fillColor: p.offsite ? "#C0392B" : "#2E7D5B", fillOpacity: 0.9 }}>
              <Popup>{p.filename}: {p.offsite ? `OFF-SITE, ${p.km_from_campus} km from campus` : `on site (${p.km_from_campus} km)`}</Popup>
            </CircleMarker>
          ))}
        </MapContainer>
        {dev != null && (
          <p className={dev > 0.15 ? "err" : "ok"}>Built-up area: declared {d.declared_built_up_total_m2.toLocaleString()} sq m vs {expected.toLocaleString()} sq m expected from footprints × floors ({(dev * 100).toFixed(1)}% difference; limit 15%).</p>
        )}
      </section>
      <section className="card">
        <h2>Photos</h2>
        <div className="gallery">
          {d.photos.map((p: J) => {
            const dup = dupOf(p.document_id);
            const label = docs.find((x) => x.id === p.document_id)?.filename ?? p.filename;
            return (
              <figure key={p.document_id} className={p.offsite || dup?.severity === "MAJOR" ? "bad" : ""}>
                <Img path={`/documents/${p.document_id}/pages/1.png`} alt={`Photo ${label}`} width={260} />
                <figcaption>
                  <strong>{label}</strong>
                  <div className="small">{p.taken_at?.slice(0, 10)} · {p.km_from_campus != null ? `${p.km_from_campus} km from campus` : "no GPS"}</div>
                  {p.offsite && <span className="chip red">Off-site GPS</span>}
                  {dup && <span className={`chip ${dup.severity === "MAJOR" ? "red" : "grey"}`}>{dup.severity === "MAJOR" ? "Near-copy of another institution's photo" : "Reused by another institution"}</span>}
                </figcaption>
              </figure>
            );
          })}
        </div>
        {d.duplicates.filter((x: J) => x.severity === "MAJOR").map((x: J) => (
          <div key={x.flag_id} className="dupe">
            <h3>Duplicate photo, side by side</h3>
            <div className="row gap">
              <figure><Img path={`/documents/${x.photo_document_id}/pages/1.png`} alt="This institution's photo" width={380} /><figcaption>This institution</figcaption></figure>
              <figure><Img path={`/documents/${x.other_document_id}/pages/1.png`} alt="Matching photo from another institution" width={380} /><figcaption>Other institution (perceptual-hash distance {x.distance}/64)</figcaption></figure>
            </div>
          </div>
        ))}
      </section>
    </>
  );
}
