const LS_KEY = "gerente_api_key";

export function getApiKey(): string {
  return localStorage.getItem(LS_KEY) || "";
}

export function setApiKey(key: string) {
  if (key) localStorage.setItem(LS_KEY, key);
  else localStorage.removeItem(LS_KEY);
}

function base(): string {
  const v = import.meta.env.VITE_API_BASE;
  return typeof v === "string" && v.length ? v.replace(/\/$/, "") : "";
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const key = getApiKey();
  const headers = new Headers(init.headers);
  if (key) headers.set("Authorization", `Bearer ${key}`);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const url = `${base()}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || res.statusText);
  }
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type");
  if (ct?.includes("application/json")) return res.json();
  return res.text();
}
