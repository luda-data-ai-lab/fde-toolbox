import { create } from "zustand";
import { persist } from "zustand/middleware";

interface WorkspaceState {
  tenantId: string | null;
  engagementId: string | null;
  setTenant: (id: string | null) => void;
  setEngagement: (id: string | null) => void;
}

export const useWorkspace = create<WorkspaceState>()(
  persist(
    (set) => ({
      tenantId: null,
      engagementId: null,
      setTenant: (tenantId) => set({ tenantId, engagementId: null }),
      setEngagement: (engagementId) => set({ engagementId }),
    }),
    { name: "fde-workspace" },
  ),
);
