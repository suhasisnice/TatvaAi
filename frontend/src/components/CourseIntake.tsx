import { useEffect, useState } from "react";
import { api, J } from "../api";
import { ErrorBox } from "../ui";

type Course = { course: string; level: string; intake: number; duration: number };

/** Course & intake settings: the faculty, room and computer norms are computed from these numbers (feature map: supports Feature 1). */
export default function CourseIntake({ appId, programmes, locked, onSaved }: { appId: number; programmes: J[]; locked: boolean; onSaved: () => void }) {
  const [rows, setRows] = useState<Course[]>([]);
  const [err, setErr] = useState("");
  const [saved, setSaved] = useState("");
  useEffect(() => { setRows((programmes ?? []).map((p) => ({ course: p.course, level: p.level, intake: p.intake, duration: p.duration ?? 4 }))); }, [programmes]);
  const set = (i: number, patch: Partial<Course>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const total = rows.reduce((n, r) => n + (Number(r.intake) || 0) * (Number(r.duration) || 0), 0);
  const save = async () => {
    setErr(""); setSaved("");
    try { await api(`/applications/${appId}`, { method: "PATCH", body: JSON.stringify({ form: { programmes: rows.map((r) => ({ ...r, intake: Number(r.intake), duration: Number(r.duration) })) } }) }); setSaved("Course and intake saved."); onSaved(); }
    catch (e) { setErr((e as Error).message); }
  };
  return (
    <section className="card">
      <h2>Course &amp; intake</h2>
      <p className="muted">Approved intake per course. Required faculty, rooms, laboratories, computers and bandwidth are calculated from these numbers (S = intake × course years = {total}).</p>
      <table>
        <thead><tr><th>Course</th><th>Level</th><th>Intake per year</th><th>Years</th>{!locked && <th />}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {locked ? (<><td>{r.course}</td><td>{r.level}</td><td>{r.intake}</td><td>{r.duration}</td></>) : (<>
                <td><input aria-label={`Course ${i + 1} name`} value={r.course} onChange={(e) => set(i, { course: e.target.value })} /></td>
                <td><select aria-label={`Course ${i + 1} level`} value={r.level} onChange={(e) => set(i, { level: e.target.value })}>{["UG", "PG", "DIPLOMA"].map((l) => <option key={l}>{l}</option>)}</select></td>
                <td><input aria-label={`Course ${i + 1} intake`} type="number" min={1} max={2000} value={r.intake} onChange={(e) => set(i, { intake: Number(e.target.value) })} /></td>
                <td><input aria-label={`Course ${i + 1} years`} type="number" min={1} max={6} value={r.duration} onChange={(e) => set(i, { duration: Number(e.target.value) })} /></td>
                <td><button type="button" onClick={() => setRows(rows.filter((_, j) => j !== i))} disabled={rows.length < 2}>Remove</button></td>
              </>)}
            </tr>
          ))}
        </tbody>
      </table>
      {!locked && (
        <div className="row gap">
          <button type="button" onClick={() => setRows([...rows, { course: "", level: "UG", intake: 60, duration: 4 }])}>Add course</button>
          <button type="button" className="primary" onClick={save}>Save course &amp; intake</button>
        </div>
      )}
      {saved && <p role="status" className="ok">{saved}</p>}<ErrorBox message={err} />
    </section>
  );
}
