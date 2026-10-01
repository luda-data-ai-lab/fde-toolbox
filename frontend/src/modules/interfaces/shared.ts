import { useQuery } from "@tanstack/react-query";
import { api, tenantPath } from "../../api/client";
import type { Page, System } from "../../api/types";

export const LINK_TYPES = [
  "db_link",
  "api",
  "file",
  "mq",
  "eai",
  "other",
] as const;
export const IF_STATUSES = [
  "planned",
  "developing",
  "operating",
  "retired",
] as const;

export function useSystems(tenantId: string | null) {
  return useQuery({
    queryKey: ["systems", tenantId],
    queryFn: () =>
      api<Page<System>>(tenantPath(tenantId, "/systems"), {
        query: { limit: 200 },
      }),
    enabled: !!tenantId,
  });
}

export function ifKeys(tenantId: string | null) {
  return {
    all: ["interfaces", tenantId] as const,
    list: (filters: object) =>
      ["interfaces", tenantId, "list", filters] as const,
    dashboard: ["interfaces", tenantId, "dashboard"] as const,
    graph: (filters: object) =>
      ["interfaces", tenantId, "graph", filters] as const,
  };
}
