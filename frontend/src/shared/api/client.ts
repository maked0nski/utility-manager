import { API_BASE, TOKEN_KEY } from "@/shared/constants/app";
import type { ApiErrorPayload, ApiRequestOptions } from "@/shared/api/types";

function normalizeBody(body: ApiRequestOptions["body"]): BodyInit | null | undefined {
  if (body === undefined || body === null) return body;
  if (body instanceof FormData) return body;
  if (typeof body === "string") return body;
  return JSON.stringify(body);
}

export async function api<T = unknown>(
  path: string,
  token: string | null | undefined,
  options: ApiRequestOptions = {},
): Promise<T> {
  const headers: HeadersInit = { ...(options.headers || {}) };
  const body = normalizeBody(options.body);
  if (!(body instanceof FormData) && !(headers as Record<string, string>)["Content-Type"]) {
    (headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  if (token) (headers as Record<string, string>).Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, body, headers });
  const data = (await res.json().catch(() => ({}))) as T | ApiErrorPayload;

  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("um-unauthorized"));
    }
  }

  if (!res.ok) {
    const payload = data as ApiErrorPayload;
    throw new Error(typeof payload.detail === "string" ? payload.detail : "Request failed");
  }
  return data as T;
}
