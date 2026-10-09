import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api, tenantPath } from "../../api/client";
import type {
  CandidateExtractResult,
  CandidateSuggestPrompt,
  DiscoverySession,
  MappingSources,
  OntoCandidate,
  OntoConcept,
  Page,
} from "../../api/types";
import {
  Empty,
  ErrorText,
  Field,
  Select,
  StatusBadge,
} from "../../components/ui";
import { useCanWrite } from "../../app/hooks";
import {
  CANDIDATE_KINDS,
  CANDIDATE_SOURCES,
  CANDIDATE_STATUSES,
  EXTRACT_SOURCES,
  SUGGEST_TASKS,
  ontoKeys,
  ontoPath,
} from "./shared";

type Option = { id: string; name: string };

function useConceptOptions(tenantId: string, enabled: boolean) {
  return useQuery({
    queryKey: [...ontoKeys(tenantId).concepts, "options"],
    queryFn: () =>
      api<Page<OntoConcept>>(ontoPath(tenantId, "/concepts"), {
        query: { limit: 200 },
      }),
    enabled,
  });
}

function useSystemOptions(tenantId: string, enabled: boolean) {
  return useQuery({
    queryKey: ontoKeys(tenantId).sources,
    queryFn: () => api<MappingSources>(ontoPath(tenantId, "/mapping-sources")),
    enabled,
  });
}

function IdSelect({
  label,
  value,
  onChange,
  options,
  emptyLabel,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: Option[];
  emptyLabel: string;
}) {
  return (
    <Field label={label}>
      <select
        className="input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{emptyLabel}</option>
        {options.map((o) => (
          <option key={o.id} value={o.id}>
            {o.name}
          </option>
        ))}
      </select>
    </Field>
  );
}

function sourceLink(c: OntoCandidate): string | null {
  if (!c.source_id) return null;
  if (c.source_type === "discovery_session")
    return `/discoveryq?tab=sessions&session=${c.source_id}`;
  if (c.source_type === "flowdesk_flow") return `/flowdesk?flow=${c.source_id}`;
  if (c.source_type === "exmigrate_erd")
    return `/exmigrate?analysis=${c.source_id}`;
  return null;
}

function provenance(c: OntoCandidate): string | null {
  const p = c.payload;
  if (c.kind === "attribute" && p.table)
    return `${p.concept ?? ""} · ${p.table}.${p.column ?? ""}`;
  if (c.kind === "relation")
    return p.column
      ? `${p.relation ?? ""} · ${p.table ?? ""}.${p.column}`
      : null;
  if (p.if_code) return p.if_code;
  if (p.flow) return p.flow;
  if (p.table) return p.table;
  return null;
}

function CandidateRow({ tenantId, c }: { tenantId: string; c: OntoCandidate }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const open = c.status === "open";
  const [definition, setDefinition] = useState(c.payload.definition ?? "");
  const [name, setName] = useState("");
  const [systemId, setSystemId] = useState("");
  const [conceptId, setConceptId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [targetId, setTargetId] = useState("");
  const needsConcepts =
    open && canWrite && (c.kind === "attribute" || c.kind === "relation");
  const concepts = useConceptOptions(tenantId, needsConcepts);
  const systems = useSystemOptions(
    tenantId,
    open && canWrite && c.kind === "concept",
  );
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
  const accept = () => {
    const body: Record<string, unknown> = { term: name.trim() || null };
    if (c.kind === "term" || c.kind === "concept")
      body.definition = definition || null;
    if (c.kind === "concept") body.system_id = systemId || null;
    if (c.kind === "attribute") body.concept_id = conceptId || null;
    if (c.kind === "relation") {
      body.source_concept_id = sourceId || null;
      body.target_concept_id = targetId || null;
    }
    act.mutate({ op: "accept", body });
  };
  const link = sourceLink(c);
  const where = provenance(c);
  const conceptOptions = (concepts.data?.items ?? []).map((x) => ({
    id: x.id,
    name: x.name,
  }));
  const auto = t("ontomap.candidate.auto");
  return (
    <li className="card space-y-2" data-testid="candidate-row">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="badge">{t(`candidateKind.${c.kind}`)}</span>{" "}
          <span className="font-medium">{c.name}</span>{" "}
          <StatusBadge group="candidateStatus" value={c.status} />{" "}
          {c.payload.department && (
            <span className="badge">{c.payload.department}</span>
          )}
          {link ? (
            <Link className="ml-2 text-xs text-blue-700 underline" to={link}>
              {t(`candidateSource.${c.source_type}`)}
            </Link>
          ) : (
            <span className="ml-2 text-xs text-slate-500">
              {t(`candidateSource.${c.source_type}`)}
            </span>
          )}
          {where && (
            <span className="ml-2 text-xs text-slate-500">{where}</span>
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
      {open && c.payload.definition && c.payload.task === "definitions" && (
        <p className="text-sm text-slate-600">
          {t("ontomap.field.definition")}: {c.payload.definition}
        </p>
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
                    act.mutate({ op: "merge", body: { target_id: s.term_id } })
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
        <div className="flex flex-wrap items-end gap-2">
          {c.kind !== "term" && (
            <div className="w-48">
              <Field label={t("ontomap.candidate.name")}>
                <input
                  className="input"
                  value={name}
                  placeholder={
                    c.kind === "attribute"
                      ? c.payload.attribute
                      : c.kind === "relation"
                        ? c.payload.relation
                        : c.name
                  }
                  onChange={(e) => setName(e.target.value)}
                />
              </Field>
            </div>
          )}
          {(c.kind === "term" || c.kind === "concept") && (
            <div className="min-w-48 flex-1">
              <Field label={t("ontomap.field.definition")}>
                <input
                  className="input"
                  value={definition}
                  onChange={(e) => setDefinition(e.target.value)}
                />
              </Field>
            </div>
          )}
          {c.kind === "concept" && (
            <IdSelect
              label={t("ontomap.candidate.system")}
              value={systemId}
              onChange={setSystemId}
              options={systems.data?.systems ?? []}
              emptyLabel={t("common.none")}
            />
          )}
          {c.kind === "attribute" && (
            <IdSelect
              label={t("ontomap.candidate.concept")}
              value={conceptId}
              onChange={setConceptId}
              options={conceptOptions}
              emptyLabel={auto}
            />
          )}
          {c.kind === "relation" && (
            <>
              <IdSelect
                label={t("ontomap.candidate.sourceConcept")}
                value={sourceId}
                onChange={setSourceId}
                options={conceptOptions}
                emptyLabel={auto}
              />
              <IdSelect
                label={t("ontomap.candidate.targetConcept")}
                value={targetId}
                onChange={setTargetId}
                options={conceptOptions}
                emptyLabel={auto}
              />
            </>
          )}
          <button className="btn btn-primary" onClick={accept}>
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

function Extracted({ result }: { result: CandidateExtractResult }) {
  const { t } = useTranslation();
  return (
    <p className="text-sm text-slate-600" role="status">
      {t("ontomap.candidate.extracted", {
        created: result.created,
        existing: result.existing,
      })}
    </p>
  );
}

function ExtractPanel({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const run = useMutation({
    mutationFn: (source_type: string) =>
      api<CandidateExtractResult>(ontoPath(tenantId, "/candidates/extract"), {
        method: "POST",
        body: { source_type },
      }),
    onSuccess: () =>
      void qc.invalidateQueries({ queryKey: ontoKeys(tenantId).all }),
  });
  return (
    <section
      className="card space-y-2"
      aria-label={t("ontomap.candidate.extractTitle")}
    >
      <h2 className="font-semibold">{t("ontomap.candidate.extractTitle")}</h2>
      <p className="text-sm text-slate-600">
        {t("ontomap.candidate.extractHint")}
      </p>
      <div className="flex flex-wrap gap-2">
        {EXTRACT_SOURCES.map((s) => (
          <button
            key={s}
            className="btn"
            type="button"
            disabled={run.isPending}
            onClick={() => run.mutate(s)}
          >
            {t(`ontomap.candidate.extractFrom.${s}`)}
          </button>
        ))}
      </div>
      {run.data && <Extracted result={run.data} />}
      <ErrorText error={run.error} />
    </section>
  );
}

function SuggestPanel({ tenantId }: { tenantId: string }) {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const [task, setTask] = useState<string>("terms");
  const [sessionId, setSessionId] = useState("");
  const [answer, setAnswer] = useState("");
  const [copied, setCopied] = useState(false);
  const sessions = useQuery({
    queryKey: ["discoveryq", tenantId, "sessions", "options"],
    queryFn: () =>
      api<Page<DiscoverySession>>(
        tenantPath(tenantId, "/discoveryq/sessions"),
        {
          query: { limit: 200 },
        },
      ),
  });
  const body = () => ({
    task,
    session_id: task === "terms" ? sessionId || null : null,
    lang: i18n.language.startsWith("en") ? "en" : "ko",
  });
  const prompt = useMutation({
    mutationFn: () =>
      api<CandidateSuggestPrompt>(
        ontoPath(tenantId, "/candidates/suggest/prompt"),
        { method: "POST", body: body() },
      ),
    onSuccess: () => setCopied(false),
  });
  const run = useMutation({
    mutationFn: (pasted: string | null) =>
      api<CandidateExtractResult>(ontoPath(tenantId, "/candidates/suggest"), {
        method: "POST",
        body: { ...body(), answer: pasted },
      }),
    onSuccess: () => {
      setAnswer("");
      void qc.invalidateQueries({ queryKey: ontoKeys(tenantId).all });
    },
  });
  const reset = () => {
    prompt.reset();
    run.reset();
  };
  const ready = task !== "terms" || !!sessionId;
  const copy = async () => {
    if (!prompt.data) return;
    await navigator.clipboard.writeText(prompt.data.prompt);
    setCopied(true);
  };
  return (
    <section className="card space-y-3" aria-label={t("ontomap.suggest.title")}>
      <h2 className="font-semibold">{t("ontomap.suggest.title")}</h2>
      <p className="text-sm text-slate-600">{t("ontomap.suggest.intro")}</p>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label={t("ontomap.suggest.task")}>
          <Select
            value={task}
            onChange={(v) => {
              setTask(v);
              reset();
            }}
            options={SUGGEST_TASKS}
            group="suggestTask"
          />
        </Field>
        {task === "terms" && (
          <IdSelect
            label={t("ontomap.suggest.session")}
            value={sessionId}
            onChange={(v) => {
              setSessionId(v);
              reset();
            }}
            options={(sessions.data?.items ?? []).map((s) => ({
              id: s.id,
              name: s.title,
            }))}
            emptyLabel={t("common.none")}
          />
        )}
      </div>
      <div className="flex flex-wrap gap-3">
        <button
          className="btn"
          type="button"
          disabled={!ready || prompt.isPending}
          onClick={() => prompt.mutate()}
        >
          {t("ontomap.suggest.makePrompt")}
        </button>
        {prompt.data?.llm_available && (
          <button
            className="btn btn-primary"
            type="button"
            disabled={!ready || run.isPending}
            onClick={() => run.mutate(null)}
          >
            {run.isPending
              ? t("ontomap.suggest.running")
              : t("ontomap.suggest.runLlm")}
          </button>
        )}
      </div>
      {prompt.data && (
        <div className="space-y-3">
          <Field label={t("ontomap.suggest.prompt")}>
            <textarea
              className="input min-h-40 font-mono text-xs"
              readOnly
              value={prompt.data.prompt}
            />
          </Field>
          <button className="btn" type="button" onClick={() => void copy()}>
            {copied ? t("ontomap.suggest.copied") : t("ontomap.suggest.copy")}
          </button>
          <Field label={t("ontomap.suggest.answer")}>
            <textarea
              className="input min-h-32 font-mono text-xs"
              value={answer}
              placeholder={t("ontomap.suggest.answerHint")}
              onChange={(e) => setAnswer(e.target.value)}
            />
          </Field>
          <button
            className="btn btn-primary"
            type="button"
            disabled={!answer.trim() || run.isPending}
            onClick={() => run.mutate(answer)}
          >
            {t("ontomap.suggest.fromAnswer")}
          </button>
        </div>
      )}
      {run.data && <Extracted result={run.data} />}
      <ErrorText error={prompt.error ?? run.error} />
    </section>
  );
}

export function CandidatesView({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const [status, setStatus] = useState("open");
  const [kind, setKind] = useState("");
  const [source, setSource] = useState("");
  const filters = { status, kind, source_type: source };
  const { data } = useQuery({
    queryKey: ontoKeys(tenantId).candidates(filters),
    queryFn: () =>
      api<Page<OntoCandidate>>(ontoPath(tenantId, "/candidates"), {
        query: { ...filters, limit: 200 },
      }),
  });
  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="grid gap-4 lg:grid-cols-2">
          <ExtractPanel tenantId={tenantId} />
          <SuggestPanel tenantId={tenantId} />
        </div>
      )}
      <div className="card grid grid-cols-4 gap-3">
        <Field label={t("common.status")}>
          <Select
            value={status}
            onChange={setStatus}
            options={CANDIDATE_STATUSES}
            group="candidateStatus"
            allowEmpty
          />
        </Field>
        <Field label={t("ontomap.candidate.kind")}>
          <Select
            value={kind}
            onChange={setKind}
            options={CANDIDATE_KINDS}
            group="candidateKind"
            allowEmpty
          />
        </Field>
        <Field label={t("ontomap.candidate.source")}>
          <Select
            value={source}
            onChange={setSource}
            options={CANDIDATE_SOURCES}
            group="candidateSource"
            allowEmpty
          />
        </Field>
        <p className="self-end text-sm text-slate-500">
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
