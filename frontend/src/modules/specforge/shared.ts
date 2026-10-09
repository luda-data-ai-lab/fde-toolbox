import { tenantPath } from "../../api/client";

export const DOC_TYPES = ["spec", "devin"] as const;

export function specPath(tenantId: string | null, path: string): string {
  return tenantPath(tenantId, `/specforge${path}`);
}

export function specKeys(tenantId: string | null) {
  return {
    all: ["specforge", tenantId] as const,
    list: (filters: object) => ["specforge", tenantId, "documents", filters] as const,
    doc: (id: string) => ["specforge", tenantId, "doc", id] as const,
    versions: (id: string) => ["specforge", tenantId, "versions", id] as const,
    templates: ["specforge", tenantId, "templates"] as const,
    rulePacks: ["specforge", tenantId, "rule-packs"] as const,
  };
}

/** Toggle `id` in a list of selected ids. */
export function toggle(ids: string[], id: string): string[] {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
}
