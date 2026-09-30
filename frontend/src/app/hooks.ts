import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Asset, Me, Role } from "../api/types";
import { useWorkspace } from "./store";

export const WRITE_ROLES: Role[] = ["luda_admin", "fde"];
export const AUDIT_ROLES: Role[] = ["luda_admin", "fde", "client_admin"];

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/auth/me"), retry: false, staleTime: 60_000 });
}

export function useRole(): Role | undefined {
  return useMe().data?.user.role;
}

export function useCanWrite(): boolean {
  const role = useRole();
  return role !== undefined && WRITE_ROLES.includes(role);
}

/** Current tenant id, only if the signed-in user may access it. */
export function useTenantId(): string | null {
  const { data } = useMe();
  const tenantId = useWorkspace((s) => s.tenantId);
  if (!data || !tenantId) return null;
  return data.tenants.some((t) => t.id === tenantId) ? tenantId : null;
}

export function useAssetVersions(assetId: string | undefined) {
  return useQuery({
    queryKey: ["asset", assetId],
    queryFn: () => api<Asset[]>(`/assets/${assetId}`),
    enabled: !!assetId,
  });
}
