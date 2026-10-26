import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell } from "lucide-react";
import { api } from "../lib/api";

const KIND_LABEL: Record<string, string> = {
  MISSING_INFO: "Missing information",
  DOC_EXPIRING: "Expiry",
  DOC_EXPIRED: "Expired",
  ANOMALY: "Suspected anomaly",
};

export default function AlertBell({ role }: { role: string }) {
  const [data, setData] = useState<{ unread: number; alerts: any[] }>({ unread: 0, alerts: [] });
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  function load() {
    api.alerts().then(setData).catch(() => {});
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  async function openAlert(a: any) {
    if (!a.read) await api.markAlertRead(a.id);
    setOpen(false);
    load();
    navigate(role === "institution" ? `/institution/applications/${a.application_id}` : `/officer/applications/${a.application_id}`);
  }

  if (role === "inspector") return null;

  return (
    <div className="bell" ref={ref}>
      <button className="bell-btn" onClick={() => setOpen(!open)} aria-label="Alerts">
        <Bell size={18} />
        {data.unread > 0 && <span className="bell-count">{data.unread}</span>}
      </button>
      {open && (
        <div className="bell-panel">
          <div className="bell-title">Alerts</div>
          {data.alerts.length === 0 && <div className="bell-empty">Nothing needs attention.</div>}
          {data.alerts.map(a => (
            <div key={a.id} className={`bell-item ${a.read ? "read" : ""}`} onClick={() => openAlert(a)}>
              <div className="bell-kind">{KIND_LABEL[a.kind] || a.kind}</div>
              <div>{a.message}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
