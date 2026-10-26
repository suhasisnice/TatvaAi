import { useEffect, useState } from "react";
import { api, ApiError, J, post } from "../../api";
import { useApi } from "../../hooks";
import { ErrorBox, fmtDate, Loading, RiskChip } from "../../ui";

export default function Rules() {
  const packs = useApi<J[]>("/rulepacks");
  const [sel, setSel] = useState("");
  const [yaml, setYaml] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [msg, setMsg] = useState("");
  const [diff, setDiff] = useState<J>(null);
  const [busy, setBusy] = useState("");
  const [folder, setFolder] = useState("APH-2024-27-v2-demo");
  const pack = packs.data?.find((p) => p.version === sel);

  useEffect(() => {
    if (!sel) return;
    api<J>(`/rulepacks/${sel}`).then((p) => { setYaml(p.yaml); setErrors([]); setDiff(null); setMsg(""); });
  }, [sel]);
  useEffect(() => { if (!sel && packs.data?.length) setSel(packs.data.find((p) => p.status === "active")?.version ?? packs.data[0].version); }, [packs.data, sel]);

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label); setMsg(""); setErrors([]);
    try { await fn(); } catch (e) { setErrors(e instanceof ApiError && e.detail?.errors ? e.detail.errors : [(e as Error).message]); } finally { setBusy(""); }
  };
  const validate = () => run("validate", async () => { const r = await post<J>("/rulepacks/validate-yaml", { yaml }); setErrors(r.errors); setMsg(r.valid ? "Valid: schema, ids and expressions are fine." : ""); });
  const save = () => run("save", async () => { const r = await post<J>("/rulepacks", { yaml }); setMsg(`Saved ${r.version} as a draft (${r.rule_count} rules).`); packs.reload(); setSel(r.version); });
  const importDir = () => run("import", async () => { const r = await post<J>("/rulepacks", { from_dir: folder }); setMsg(`Created ${r.version} as a draft from the rulepacks folder.`); packs.reload(); setSel(r.version); });
  const dry = () => run("dry", async () => setDiff(await post<J>(`/rulepacks/${sel}/dry-run`)));
  const activate = () => {
    if (!confirm(`Activate rule pack ${sel}?\n\nNew validations will use it. Results already produced under other versions are not changed.`)) return;
    return run("activate", async () => { await post(`/rulepacks/${sel}/activate`); setMsg(`${sel} is now the active rule pack.`); packs.reload(); });
  };

  return (
    <>
      <h1>Rule packs: the Handbook as code</h1>
      <p className="muted">Exactly one pack is active. Packs are immutable once created: to change a rule, edit the YAML, change the version, and save a new draft. Then dry-run, then activate.</p>
      <div className="split wide-left">
        <section className="card left">
          <h2>Versions</h2>
          {packs.loading && <Loading />}
          <table>
            <thead><tr><th>Version</th><th>Status</th><th>Rules</th><th>Effective</th></tr></thead>
            <tbody>
              {(packs.data ?? []).map((p) => (
                <tr key={p.version} className={p.version === sel ? "selected" : ""}>
                  <td><button className="linkish" onClick={() => setSel(p.version)}>{p.version}</button></td>
                  <td><span className={`chip ${p.status === "active" ? "green" : p.status === "draft" ? "blue" : "grey"}`}>{p.status}</span></td>
                  <td>{p.rule_count}</td><td>{fmtDate(p.effective_from)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="row gap end">
            <label>Create from rulepacks folder<input value={folder} onChange={(e) => setFolder(e.target.value)} /></label>
            <button onClick={importDir} disabled={!!busy}>Create draft</button>
          </div>
        </section>
        <section className="card right">
          <div className="row between">
            <h2>{sel ? `Editor: ${sel}` : "Editor"}</h2>
            <div className="row gap">
              <button onClick={validate} disabled={!!busy || !yaml}>Validate</button>
              <button onClick={save} disabled={!!busy || !yaml}>Save as new draft</button>
              <button onClick={dry} disabled={!!busy || !pack}>Dry-run</button>
              <button className="primary" onClick={activate} disabled={!!busy || !pack || pack.status === "active"}>Activate</button>
            </div>
          </div>
          <textarea className="yaml" aria-label="Rule pack YAML" spellCheck={false} value={yaml} onChange={(e) => setYaml(e.target.value)} rows={18} />
          {msg && <p role="status" className="ok">{msg}</p>}
          {errors.length > 0 && <ul role="alert" className="errlist">{errors.map((e, i) => <li key={i}>{e}</li>)}</ul>}
          <ErrorBox message={packs.error} />
        </section>
      </div>
      {diff && (
        <section className="card">
          <h2>Dry-run of {diff.draft_version}: {diff.applications_changed} application(s) would change ({diff.tier_changes} tier change{diff.tier_changes === 1 ? "" : "s"})</h2>
          <p className="muted">Nothing has been changed. Current results stay under their own rule pack version.</p>
          <table>
            <thead><tr><th>Application</th><th>Risk now</th><th>Risk under {diff.draft_version}</th><th>Flags appearing</th><th>Flags disappearing</th><th>Wording changes</th></tr></thead>
            <tbody>
              {diff.changes.map((c: J) => (
                <tr key={c.application_id}>
                  <td><strong>{c.institution_name}</strong><div className="muted small">AY {c.academic_year}</div></td>
                  <td><RiskChip tier={c.tier_before} score={c.score_before} /></td>
                  <td><RiskChip tier={c.tier_after} score={c.score_after} />{c.tier_changed && <div className="small"><b>Tier changes</b></div>}</td>
                  <td>{c.flags_added.map((f: J) => <div key={f.code + f.message}><code>{f.code}</code> {f.message}</div>)}</td>
                  <td>{c.flags_removed.map((f: J) => <div key={f.code + f.message}><code>{f.code}</code></div>)}</td>
                  <td className="small">{c.flags_reworded.map((f: J) => <div key={f.code}>{f.before} → <b>{f.after}</b></div>)}</td>
                </tr>
              ))}
              {diff.changes.length === 0 && <tr><td colSpan={6} className="muted">No application would change.</td></tr>}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}
