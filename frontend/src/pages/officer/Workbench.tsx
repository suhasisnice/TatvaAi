import { FileDown, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import AuditTab from "../../components/wb/AuditTab";
import Compliance from "../../components/wb/Compliance";
import Flags from "../../components/wb/Flags";
import Infrastructure from "../../components/wb/Infrastructure";
import Summary from "../../components/wb/Summary";
import Timeline from "../../components/wb/Timeline";
import Verification from "../../components/wb/Verification";
import { download, J, post, User } from "../../api";
import { useApi } from "../../hooks";
import { ErrorBox, Loading, RiskChip, Tabs } from "../../ui";

const TABS: [string, string][] = [["summary", "Summary"], ["flags", "Flags & Evidence"], ["verification", "Verification"], ["compliance", "Compliance"], ["infra", "Infrastructure"], ["timeline", "Timeline"], ["audit", "Audit"]];

export default function Workbench({ user }: { user: User }) {
  const { id } = useParams();
  const [sp, setSp] = useSearchParams();
  const tab = sp.get("tab") ?? "summary";
  const app = useApi<J>(`/applications/${id}`);
  const docs = useApi<J[]>(`/applications/${id}/documents`);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const a = app.data;
  if (!a) return app.error ? <ErrorBox message={app.error} /> : <Loading />;
  const d = docs.data ?? [];
  const appId = Number(id);
  const rerun = async () => { setBusy("rerun"); setErr(""); try { await post(`/applications/${id}/verify`); app.reload(); docs.reload(); } catch (e) { setErr((e as Error).message); } finally { setBusy(""); } };

  return (
    <>
      <div className="wb-head">
        <div>
          <Link to="/officer" className="muted">← Review queue</Link>
          <h1>{a.institution_name}</h1>
          <p className="muted">{a.state} · AICTE ID {a.aicte_id} · {a.category.replaceAll("_", " ")} · AY {a.academic_year} · {a.status}</p>
        </div>
        <div className="col end">
          <RiskChip tier={a.risk?.tier} score={a.risk?.score} />
          <div className="row gap">
            <button onClick={rerun} disabled={!!busy}><RefreshCw size={15} aria-hidden /> {busy ? "Validating…" : "Re-run validation"}</button>
            <button onClick={() => download(`/applications/${id}/report.pdf`, `tatvaai-report-${id}.pdf`).catch((e) => setErr(e.message))}><FileDown size={15} aria-hidden /> Validation report (PDF)</button>
          </div>
        </div>
      </div>
      <ErrorBox message={err} />
      <Tabs tabs={TABS} active={tab} onChange={(k) => setSp({ tab: k })} />
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "summary" && <Summary app={a} docs={d} />}
        {tab === "flags" && <Flags appId={appId} docs={d} canDecide={user.role === "officer"} onChanged={app.reload} focusFlagId={Number(sp.get("flag")) || undefined} />}
        {tab === "verification" && <Verification appId={appId} docs={d} canConfirm={user.role === "officer"} />}
        {tab === "compliance" && <Compliance appId={appId} />}
        {tab === "infra" && <Infrastructure appId={appId} docs={d} />}
        {tab === "timeline" && <Timeline appId={appId} docs={d} />}
        {tab === "audit" && <AuditTab appId={appId} />}
      </div>
    </>
  );
}
