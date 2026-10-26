const BASE = "http://127.0.0.1:8010";

export type Session = { token: string; role: string; name: string; institutionId: number | null };

function getSession(): Session | null {
  const raw = localStorage.getItem("tatvai_session");
  return raw ? JSON.parse(raw) : null;
}

function setSession(s: Session | null) {
  if (s) localStorage.setItem("tatvai_session", JSON.stringify(s));
  else localStorage.removeItem("tatvai_session");
}

async function request(path: string, opts: RequestInit = {}) {
  const session = getSession();
  const headers: Record<string, string> = { ...(opts.headers as any) };
  if (session) headers["Authorization"] = `Bearer ${session.token}`;
  if (!(opts.body instanceof FormData) && opts.body) headers["Content-Type"] = "application/json";
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch {}
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  getSession,
  setSession,
  async login(email: string, password: string): Promise<Session> {
    const data = await request("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
    const session: Session = { token: data.access_token, role: data.role, name: data.name, institutionId: data.institution_id };
    setSession(session);
    return session;
  },
  logout() {
    setSession(null);
  },
  listApplications: () => request("/api/v1/applications"),
  createApplication: (academic_year: string, category = "EOA") =>
    request("/api/v1/applications", { method: "POST", body: JSON.stringify({ academic_year, category }) }),
  getApplication: (id: number) => request(`/api/v1/applications/${id}`),
  uploadDocument: (appId: number, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request(`/api/v1/applications/${appId}/documents`, { method: "POST", body: fd });
  },
  precheck: (appId: number) => request(`/api/v1/applications/${appId}/precheck`, { method: "POST" }),
  submit: (appId: number) => request(`/api/v1/applications/${appId}/submit`, { method: "POST" }),
  revalidate: (appId: number) => request(`/api/v1/applications/${appId}/revalidate`, { method: "POST" }),
  reopen: (appId: number) => request(`/api/v1/applications/${appId}/reopen`, { method: "POST" }),
  decideFlag: (flagId: number, decision: "ACCEPT" | "DISMISS", reason: string) =>
    request(`/api/v1/applications/flags/${flagId}/decision`, { method: "POST", body: JSON.stringify({ decision, reason }) }),
  manualVerify: (verificationId: number, note: string) =>
    request(`/api/v1/applications/verifications/${verificationId}/manual?note=${encodeURIComponent(note)}`, { method: "POST" }),
  decideInspection: (flagId: number, status: "CONFIRMED" | "CLEARED", note: string) =>
    request(`/api/v1/applications/flags/${flagId}/inspection`, { method: "POST", body: JSON.stringify({ status, note }) }),
  queue: () => request("/api/v1/risk/queue"),
  inspectionList: () => request("/api/v1/risk/inspection-list"),
  auditLog: () => request("/api/v1/audit"),
  auditVerify: () => request("/api/v1/audit/verify"),
};
