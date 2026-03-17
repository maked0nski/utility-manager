import { API_BASE } from "@/shared/constants/app";
import type { ApiErrorPayload, ApiRequestOptions, ApiValidationErrorItem } from "@/shared/api/types";

function normalizeBody(body: ApiRequestOptions["body"]): BodyInit | null | undefined {
  if (body === undefined || body === null) return body;
  if (body instanceof FormData) return body;
  if (typeof body === "string") return body;
  return JSON.stringify(body);
}

function parseValidationDetail(items: ApiValidationErrorItem[]): string | null {
  if (!Array.isArray(items) || items.length === 0) return null;
  const first = items[0];
  if (!first) return null;
  if (first.msg && first.loc?.length) {
    const field = String(first.loc[first.loc.length - 1] || "").replaceAll("_", " ");
    return field ? `${field}: ${first.msg}` : first.msg;
  }
  if (first.msg) return first.msg;
  return null;
}

function parseApiErrorMessage(payload: ApiErrorPayload): string {
  if (typeof payload?.detail === "string" && payload.detail.trim()) return payload.detail;
  if (Array.isArray(payload?.detail)) {
    const msg = parseValidationDetail(payload.detail as ApiValidationErrorItem[]);
    if (msg) return msg;
  }
  if (payload?.detail && typeof payload.detail === "object") {
    const detailObj = payload.detail as Record<string, unknown>;
    if (typeof detailObj.message === "string" && detailObj.message.trim()) return detailObj.message;
  }
  return "Request failed";
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
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("um-unauthorized"));
    }
  }

  if (!res.ok) {
    const payload = data as ApiErrorPayload;
    throw new Error(parseApiErrorMessage(payload));
  }
  return data as T;
}
