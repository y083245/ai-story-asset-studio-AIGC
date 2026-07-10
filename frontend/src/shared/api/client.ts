// =============================================================================
// Story Asset Studio — API Client
// =============================================================================
// Typed fetch wrapper. Mock mode is explicit, except local dev/test may
// fall back to mock when no API URL is configured so `next dev` still starts.
// Frontend only calls typed functions — it never understands raw model responses.
// =============================================================================

const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL?.trim();
const API_BASE = RAW_API_BASE || "";
const HAS_API_BASE = API_BASE.length > 0;
const MOCK_ENV = process.env.NEXT_PUBLIC_USE_MOCK;
const IS_LOCAL_RUNTIME = process.env.NODE_ENV !== "production";
const USE_MOCK =
  MOCK_ENV === "true" ||
  (MOCK_ENV !== "false" && !HAS_API_BASE && IS_LOCAL_RUNTIME);

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: { code?: string; message?: string; retryable?: boolean }
  ) {
    super(detail.message || `API error: ${status}`);
    this.name = "ApiError";
  }
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

async function apiFetch<T>(path: string, options?: RequestOptions): Promise<T> {
  if (USE_MOCK) {
    throw new Error(
      `Mock mode: direct apiFetch should not be called for "${path}". Use typed API modules instead.`
    );
  }

  const { body, headers: customHeaders, ...rest } = options || {};
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-User-ID": "mock-user",
    ...(customHeaders as Record<string, string>),
  };

  const res = await fetch(joinApiUrl(API_BASE, path), {
    ...rest,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail: { code?: string; message?: string; retryable?: boolean } = {};
    try {
      const payload = await res.json();
      detail = normalizeErrorPayload(payload);
    } catch {
      // ignore parse error
    }
    throw new ApiError(res.status, detail);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json();
}

function joinApiUrl(base: string, path: string): string {
  if (!base) return path;
  const normalizedBase = base.replace(/\/+$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  if (normalizedBase.endsWith("/api") && normalizedPath.startsWith("/api/")) {
    return `${normalizedBase}${normalizedPath.slice(4)}`;
  }

  return `${normalizedBase}${normalizedPath}`;
}

function normalizeErrorPayload(payload: unknown): { code?: string; message?: string; retryable?: boolean } {
  if (!payload || typeof payload !== "object") return {};

  const record = payload as Record<string, unknown>;
  const nested = record.error ?? record.detail ?? payload;
  if (!nested || typeof nested !== "object") return {};

  const detail = nested as Record<string, unknown>;
  return {
    code: typeof detail.code === "string" ? detail.code : undefined,
    message: typeof detail.message === "string" ? detail.message : undefined,
    retryable: typeof detail.retryable === "boolean" ? detail.retryable : undefined,
  };
}

export { API_BASE, USE_MOCK, apiFetch };
