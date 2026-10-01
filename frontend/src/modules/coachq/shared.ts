import { useQuery } from "@tanstack/react-query";
import { api, tenantPath } from "../../api/client";
import type {
  CoachSubject,
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

export function coachPath(tenantId: string | null, path: string): string {
  return tenantPath(tenantId, `/coachq${path}`);
}

export function coachKeys(tenantId: string | null) {
  return {
    all: ["coachq", tenantId] as const,
    bank: ["coachq", tenantId, "bank"] as const,
    subjects: (engagementId: string | null) =>
      ["coachq", tenantId, "subjects", engagementId] as const,
    custom: (engagementId: string | null) =>
      ["coachq", tenantId, "custom", engagementId] as const,
    sessions: (filters: object) =>
      ["coachq", tenantId, "sessions", filters] as const,
    worksheet: (sessionId: string) =>
      ["coachq", tenantId, "worksheet", sessionId] as const,
    actions: (filters: object) =>
      ["coachq", tenantId, "actions", filters] as const,
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
    queryKey: coachKeys(tenantId).bank,
    queryFn: () =>
      api<QuestionBankResponse>(coachPath(tenantId, "/question-bank")),
    enabled: !!tenantId,
  });
}

export function useSubjects(
  tenantId: string | null,
  engagementId: string | null,
) {
  return useQuery({
    queryKey: coachKeys(tenantId).subjects(engagementId),
    queryFn: () =>
      api<Page<CoachSubject>>(coachPath(tenantId, "/subjects"), {
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
    queryKey: coachKeys(tenantId).custom(engagementId),
    queryFn: () =>
      api<Page<CustomQuestion>>(coachPath(tenantId, "/custom-questions"), {
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
