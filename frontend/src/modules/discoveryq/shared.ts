import { useQuery } from "@tanstack/react-query";
import { api, tenantPath } from "../../api/client";
import type {
  DiscoverySubject,
  CustomQuestion,
  Engagement,
  Page,
  QuestionBankResponse,
} from "../../api/types";

export const SESSION_TYPES = ["interview", "coaching"] as const;
export const SESSION_STATUSES = ["planned", "in_progress", "done"] as const;
export const ACTION_STATUSES = [
  "open",
  "in_progress",
  "done",
  "cancelled",
] as const;

export function discoveryPath(tenantId: string | null, path: string): string {
  return tenantPath(tenantId, `/discoveryq${path}`);
}

export function discoveryKeys(tenantId: string | null) {
  return {
    all: ["discoveryq", tenantId] as const,
    bank: ["discoveryq", tenantId, "bank"] as const,
    subjects: (engagementId: string | null) =>
      ["discoveryq", tenantId, "subjects", engagementId] as const,
    custom: (engagementId: string | null) =>
      ["discoveryq", tenantId, "custom", engagementId] as const,
    sessions: (filters: object) =>
      ["discoveryq", tenantId, "sessions", filters] as const,
    worksheet: (sessionId: string) =>
      ["discoveryq", tenantId, "worksheet", sessionId] as const,
    actions: (filters: object) =>
      ["discoveryq", tenantId, "actions", filters] as const,
  };
}

export function useEngagements(tenantId: string | null) {
  return useQuery({
    queryKey: ["engagements", tenantId],
    queryFn: () =>
      api<Page<Engagement>>(tenantPath(tenantId, "/engagements"), {
        query: { limit: 200 },
      }),
    enabled: !!tenantId,
  });
}

export function useQuestionBank(tenantId: string | null) {
  return useQuery({
    queryKey: discoveryKeys(tenantId).bank,
    queryFn: () =>
      api<QuestionBankResponse>(discoveryPath(tenantId, "/question-bank")),
    enabled: !!tenantId,
  });
}

export function useSubjects(
  tenantId: string | null,
  engagementId: string | null,
) {
  return useQuery({
    queryKey: discoveryKeys(tenantId).subjects(engagementId),
    queryFn: () =>
      api<Page<DiscoverySubject>>(discoveryPath(tenantId, "/subjects"), {
        query: { limit: 200, engagement_id: engagementId },
      }),
    enabled: !!tenantId,
  });
}

export function useCustomQuestions(
  tenantId: string | null,
  engagementId: string | null,
) {
  return useQuery({
    queryKey: discoveryKeys(tenantId).custom(engagementId),
    queryFn: () =>
      api<Page<CustomQuestion>>(discoveryPath(tenantId, "/custom-questions"), {
        query: { limit: 500, engagement_id: engagementId },
      }),
    enabled: !!tenantId,
  });
}

export function splitTags(raw: string): string[] {
  return raw
    .split(/[,#\s]+/)
    .map((x) => x.trim())
    .filter(Boolean);
}
