export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public detail?: unknown,
  ) {
    super(code);
  }
}

type Body = Record<string, unknown> | unknown[] | FormData | undefined;

export async function api<T>(path: string, init: { method?: string; body?: Body; query?: Record<string, unknown> } = {}): Promise<T> {
  const url = new URL(`/api/v1${path}`, window.location.origin);
  for (const [k, v] of Object.entries(init.query ?? {})) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => url.searchParams.append(k, String(x)));
    else url.searchParams.set(k, String(v));
  }
  const isForm = init.body instanceof FormData;
  const res = await fetch(url.pathname + url.search, {
    method: init.method ?? "GET",
    credentials: "same-origin",
    headers: init.body && !isForm ? { "Content-Type": "application/json" } : undefined,
    body: init.body === undefined ? undefined : isForm ? (init.body as FormData) : JSON.stringify(init.body),
  });
  if (!res.ok) {
    let code = "errors.unknown";
    let detail: unknown;
    try {
      const data = (await res.json()) as { error?: { code?: string; message?: string; detail?: unknown } };
      code = data.error?.code ?? code;
      detail = data.error?.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, detail);
  }
  if (res.status === 204) return undefined as T;
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? await res.json() : await res.blob()) as T;
}

export function tenantPath(tenantId: string | null, path: string): string {
  if (tenantId === null) throw new Error("tenant not selected");
  return `/t/${tenantId}${path}`;
}
