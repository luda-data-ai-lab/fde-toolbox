type Value = string | string[] | boolean | null | undefined;

/** Link to another module's create screen, prefilled through query params (explicit handoff, no sync). */
export function handoffUrl(path: string, values: Record<string, Value>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(values)) {
    if (v === null || v === undefined || v === false || (Array.isArray(v) && v.length === 0) || v === "") continue;
    q.set(k, v === true ? "1" : Array.isArray(v) ? v.join(",") : v);
  }
  const s = q.toString();
  return s ? `${path}?${s}` : path;
}

export function listParam(params: URLSearchParams, key: string): string[] {
  return (params.get(key) ?? "").split(",").filter(Boolean);
}
