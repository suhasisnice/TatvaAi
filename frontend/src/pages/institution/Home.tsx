import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { J, post } from "../../api";
import { useApi } from "../../hooks";
import { ErrorBox, fmtDate, Loading } from "../../ui";

export default function InstHome() {
  const { data, error, loading } = useApi<J[]>("/applications");
  const [ay, setAy] = useState("2028-29");
  const [category, setCategory] = useState("EOA");
  const [err, setErr] = useState("");
  const nav = useNavigate();
  const create = async () => {
    try { nav(`/institution/applications/${(await post("/applications", { academic_year: ay, category })).id}`); } catch (e) { setErr((e as Error).message); }
  };
  return (
    <>
      <h1>My applications</h1>
      {loading && <Loading />}<ErrorBox message={error} />
      <div className="card">
        <table>
          <thead><tr><th>Academic year</th><th>Category</th><th>Status</th><th>Submitted</th><th /></tr></thead>
          <tbody>
            {(data ?? []).map((a) => (
              <tr key={a.id}>
                <td>{a.academic_year}</td><td>{a.category.replaceAll("_", " ")}</td>
                <td><span className={`chip ${a.locked ? "grey" : "blue"}`}>{a.status}{a.locked ? " (locked)" : ""}</span></td>
                <td>{fmtDate(a.submitted_at)}</td><td><Link to={`/institution/applications/${a.id}`}>Open</Link></td>
              </tr>
            ))}
            {data?.length === 0 && <tr><td colSpan={5} className="muted">No applications yet.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="card row gap">
        <h2>Start a new application</h2>
        <label>Academic year<input value={ay} onChange={(e) => setAy(e.target.value)} pattern="\d{4}-\d{2}" /></label>
        <label>Category
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="EOA">Extension of Approval (EoA)</option>
            <option value="INCREASE_IN_INTAKE">Increase in intake</option>
            <option value="NAME_CHANGE_INSTITUTION">Change of institution name</option>
          </select>
        </label>
        <button className="primary" onClick={create}>Create (pre-filled from last year)</button>
        <ErrorBox message={err} />
      </div>
    </>
  );
}
