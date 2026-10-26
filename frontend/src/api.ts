// ponytail: API payloads are loosely typed (J = any); add generated types from /openapi.json if the surface grows.
export type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
export type Role = "institution" | "officer" | "inspector";
export type User = { id: number; email: string; name: string; role: Role; institution_id: number | null; mfa_enabled: boolean };

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000") + "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, public detail: J) {
    super(typeof detail === "string" ? detail : detail?.errors?.join("; ") ?? JSON.stringify(detail));
  }
}

const store = {
  get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } },
  del: (k: string) => { try { localStorage.removeItem(k); } catch { /* storage unavailable */ } },
};

let refreshing: Promise<boolean> | null = null;
async function refresh(): Promise<boolean> {
  const rt = store.get("refresh");
  if (!rt) return false;
  refreshing ??= fetch(BASE + "/auth/refresh", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: rt }) })
    .then(async (r) => { if (!r.ok) return false; const t = await r.json(); store.set("access", t.access_token); store.set("refresh", t.refresh_token); return true; })
    .catch(() => false).finally(() => { refreshing = null; });
  return refreshing;
}

export async function raw(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const token = store.get("access");
  const headers: Record<string, string> = { ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(init.headers as Record<string, string>) };
  const res = await fetch(BASE + path, { ...init, headers });
  if (res.status === 401 && retry && !path.startsWith("/auth/login") && (await refresh())) return raw(path, init, false);
  return res;
}

export async function api<T = J>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await raw(path, init);
  if (!res.ok) throw new ApiError(res.status, (await res.json().catch(() => ({ detail: res.statusText }))).detail ?? res.statusText);
  return res.json();
}
export const post = <T = J>(path: string, body?: J) => api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export async function blobUrl(path: string): Promise<string> {
  const res = await raw(path);
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  return URL.createObjectURL(await res.blob());
}

export async function download(path: string, filename: string): Promise<void> {
  const url = await blobUrl(path);
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export async function login(email: string, password: string, otp?: string): Promise<User> {
  const t = await api<{ access_token: string; refresh_token: string }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password, otp: otp || undefined }) });
  store.set("access", t.access_token);
  store.set("refresh", t.refresh_token);
  return api<User>("/auth/me");
}
export const logout = () => { store.del("access"); store.del("refresh"); };
export const hasToken = () => !!store.get("access");

export const HOME: Record<Role, string> = { institution: "/institution", officer: "/officer", inspector: "/inspector" };
