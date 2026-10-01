import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { OntoCandidate, Page } from "../../api/types";
import {
  Empty,
  ErrorText,
  Field,
  Select,
  StatusBadge,
} from "../../components/ui";
import { useCanWrite } from "../../app/hooks";
import { CANDIDATE_STATUSES, ontoKeys, ontoPath } from "./shared";

function CandidateRow({ tenantId, c }: { tenantId: string; c: OntoCandidate }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const [definition, setDefinition] = useState(c.payload.definition ?? "");
  const act = useMutation({
    mutationFn: ({
      op,
      body,
    }: {
      op: string;
      body?: Record<string, unknown>;
    }) =>
      api<OntoCandidate>(ontoPath(tenantId, `/candidates/${c.id}/${op}`), {
        method: "POST",
        body: body ?? {},
      }),
    onSuccess: () =>
      void qc.invalidateQueries({ queryKey: ontoKeys(tenantId).all }),
  });
  const open = c.status === "open";
  return (
    <li className="card space-y-2" data-testid="candidate-row">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="font-medium">{c.name}</span>{" "}
          <StatusBadge group="candidateStatus" value={c.status} />{" "}
          {c.payload.department && (
            <span className="badge">{c.payload.department}</span>
          )}
          {c.source_type === "coach_session" && c.source_id && (
            <Link
              className="ml-2 text-xs text-blue-700 underline"
              to={`/coachq?tab=sessions&session=${c.source_id}`}
            >
              {t("ontomap.candidate.fromSession")}
            </Link>
          )}
        </div>
        {canWrite && c.status === "ignored" && (
          <button className="btn" onClick={() => act.mutate({ op: "reopen" })}>
            {t("ontomap.candidate.reopen")}
          </button>
        )}
      </div>
      {c.payload.context && (
        <p className="text-sm text-slate-600">“{c.payload.context}”</p>
      )}
      {open && c.similar.length > 0 && (
        <div className="text-sm" data-testid="similar">
          <span className="text-slate-500">
            {t("ontomap.candidate.similar")}:{" "}
          </span>
          {c.similar.map((s) => (
            <span
              key={s.term_id}
              className="mr-2 inline-flex items-center gap-1"
            >
              <span className="badge">
                {s.term}
                {s.matched !== s.term && ` (${s.matched})`} · {s.score}
              </span>
              {canWrite && (
                <button
                  className="btn"
                  onClick={() =>
                    act.mutate({ op: "merge", body: { term_id: s.term_id } })
                  }
                >
                  {t("ontomap.candidate.mergeInto", { term: s.term })}
                </button>
              )}
            </span>
          ))}
        </div>
      )}
      {open && canWrite && (
        <div className="flex items-end gap-2">
          <div className="flex-1">
            <Field label={t("ontomap.field.definition")}>
              <input
                className="input"
                value={definition}
                onChange={(e) => setDefinition(e.target.value)}
              />
            </Field>
          </div>
          <button
            className="btn btn-primary"
            onClick={() =>
              act.mutate({
                op: "accept",
                body: { definition: definition || null },
              })
            }
          >
            {t("ontomap.candidate.accept")}
          </button>
          <button className="btn" onClick={() => act.mutate({ op: "ignore" })}>
            {t("ontomap.candidate.ignore")}
          </button>
        </div>
      )}
      <ErrorText error={act.error} />
    </li>
  );
}

export function CandidatesView({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState("open");
  const { data } = useQuery({
    queryKey: ontoKeys(tenantId).candidates({ status }),
    queryFn: () =>
      api<Page<OntoCandidate>>(ontoPath(tenantId, "/candidates"), {
        query: { status, limit: 200 },
      }),
  });
  return (
    <div className="space-y-4">
      <div className="card grid grid-cols-3 gap-3">
        <Field label={t("common.status")}>
          <Select
            value={status}
            onChange={setStatus}
            options={CANDIDATE_STATUSES}
            group="candidateStatus"
            allowEmpty
          />
        </Field>
        <p className="col-span-2 self-end text-sm text-slate-500">
          {t("ontomap.candidate.hint")}
        </p>
      </div>
      {!data?.items.length ? (
        <div className="card">
          <Empty />
        </div>
      ) : (
        <ul className="space-y-3">
          {data.items.map((c) => (
            <CandidateRow key={c.id} tenantId={tenantId} c={c} />
          ))}
        </ul>
      )}
    </div>
  );
}
