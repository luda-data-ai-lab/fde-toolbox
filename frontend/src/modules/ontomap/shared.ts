import { tenantPath } from "../../api/client";
import type { TermAlias } from "../../api/types";

export const TERM_STATUSES = ["candidate", "confirmed", "deprecated"] as const;
export const CANDIDATE_STATUSES = [
  "open",
  "accepted",
  "merged",
  "ignored",
] as const;

export function ontoPath(tenantId: string | null, path: string): string {
  return tenantPath(tenantId, `/ontomap${path}`);
}

export function ontoKeys(tenantId: string | null) {
  return {
    all: ["ontomap", tenantId] as const,
    terms: (filters: object) =>
      ["ontomap", tenantId, "terms", filters] as const,
    candidates: (filters: object) =>
      ["ontomap", tenantId, "candidates", filters] as const,
  };
}

/** `생산팀: 배합표; BOM` ⇄ [{alias: "배합표", department: "생산팀"}, {alias: "BOM", department: null}] */
export function parseAliases(raw: string): TermAlias[] {
  return raw
    .split(/[;\n,]+/)
    .map((x) => x.trim())
    .filter(Boolean)
    .map((item) => {
      const i = item.search(/[:：]/);
      if (i < 0) return { alias: item, department: null };
      const department = item.slice(0, i).trim();
      return {
        alias: item.slice(i + 1).trim(),
        department: department || null,
      };
    })
    .filter((a) => a.alias);
}

export function formatAliases(aliases: TermAlias[]): string {
  return aliases
    .map((a) => (a.department ? `${a.department}: ${a.alias}` : a.alias))
    .join("; ");
}
