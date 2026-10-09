import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type {
  DiscoverySession,
  OntoCandidate,
  Page,
  SessionQuestion,
  Worksheet,
} from "../../api/types";
import {
  Empty,
  ErrorText,
  Field,
  Loading,
  Select,
  StatusBadge,
} from "../../components/ui";
import { handoffUrl } from "../../app/handoff";
import { AUDIT_ROLES, useCanWrite, useRole } from "../../app/hooks";
import { ontoKeys, ontoPath } from "../ontomap/shared";
import { ActionItemRow } from "./ActionItemsView";
import {
  SESSION_STATUSES,
  discoveryKeys,
  discoveryPath,
  splitTags,
  useCustomQuestions,
  useQuestionBank,
} from "./shared";

type Mutate = (body: Record<string, unknown>) => void;

function useWorksheetMutation(
  tenantId: string,
  sessionId: string,
  path: string,
  method = "POST",
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api(discoveryPath(tenantId, path), { method, body }),
    onSuccess: () =>
      void qc.invalidateQueries({ queryKey: discoveryKeys(tenantId).all }),
    mutationKey: [path, sessionId],
  });
}

function QuestionPicker({
  tenantId,
  session,
  add,
}: {
  tenantId: string;
  session: DiscoverySession;
  add: Mutate;
}) {
  const { t } = useTranslation();
  const bank = useQuestionBank(tenantId).data?.bank ?? null;
  const custom =
    useCustomQuestions(tenantId, session.engagement_id).data?.items ?? [];
  const recommended = bank?.session_types[session.type] ?? [];
  const [category, setCategory] = useState("");
  const [freeText, setFreeText] = useState("");
  const activeCategory =
    category || recommended[0] || bank?.categories[0]?.key || "";
  const questions =
    bank?.categories.find((c) => c.key === activeCategory)?.questions ?? [];
  const submitFree = (e: FormEvent) => {
    e.preventDefault();
    add({ custom_text: freeText });
    setFreeText("");
  };
  return (
    <section
      className="card space-y-3"
      aria-label={t("discoveryq.worksheet.picker")}
    >
      <h2 className="font-semibold text-slate-800">
        {t("discoveryq.worksheet.picker")}
      </h2>
      {bank && (
        <>
          <div className="flex flex-wrap gap-1" role="tablist">
            {bank.categories.map((c) => (
              <button
                key={c.key}
                role="tab"
                aria-selected={c.key === activeCategory}
                className={`badge ${c.key === activeCategory ? "bg-blue-100 text-blue-800" : ""}`}
                onClick={() => setCategory(c.key)}
              >
                {c.name}
                {recommended.includes(c.key) && " ★"}
              </button>
            ))}
          </div>
          <ul className="max-h-64 divide-y divide-slate-100 overflow-auto">
            {questions.map((q) => (
              <li
                key={q.id}
                className="flex items-center justify-between gap-2 py-1.5 text-sm"
              >
                <span>{q.text}</span>
                <button
                  className="btn shrink-0"
                  aria-label={`${t("discoveryq.worksheet.add")}: ${q.text}`}
                  onClick={() =>
                    add({
                      question_ref: {
                        asset_id: bank.asset_id,
                        version: bank.version,
                        question_id: q.id,
                      },
                    })
                  }
                >
                  {t("discoveryq.worksheet.add")}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      {custom.length > 0 && (
        <Field label={t("discoveryq.tab.custom")}>
          <select
            className="input"
            value=""
            onChange={(e) =>
              e.target.value && add({ custom_question_id: e.target.value })
            }
          >
            <option value="">{t("discoveryq.worksheet.pickCustom")}</option>
            {custom.map((q) => (
              <option key={q.id} value={q.id}>
                {q.text}
              </option>
            ))}
          </select>
        </Field>
      )}
      <form className="flex items-end gap-2" onSubmit={submitFree}>
        <div className="flex-1">
          <Field label={t("discoveryq.worksheet.freeText")}>
            <input
              className="input"
              required
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
            />
          </Field>
        </div>
        <button className="btn" type="submit">
          {t("discoveryq.worksheet.add")}
        </button>
      </form>
    </section>
  );
}

function TermRegister({
  tenantId,
  sessionId,
  questionId,
  department,
  context,
  initial,
}: {
  tenantId: string;
  sessionId: string;
  questionId: string;
  department: string | null;
  context: string;
  initial: string;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [name, setName] = useState(initial);
  const register = useMutation({
    mutationFn: () =>
      api<OntoCandidate>(ontoPath(tenantId, "/candidates"), {
        method: "POST",
        body: {
          name,
          source_type: "discovery_session",
          source_id: sessionId,
          session_question_id: questionId,
          context: context || null,
          department,
        },
      }),
    onSuccess: () => {
      setName("");
      void qc.invalidateQueries({ queryKey: ontoKeys(tenantId).all });
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    register.mutate();
  };
  return (
    <form
      className="flex items-end gap-2"
      onSubmit={submit}
      aria-label={t("ontomap.register.title")}
    >
      <div className="flex-1">
        <Field label={t("ontomap.register.term")}>
          <input
            className="input"
            required
            placeholder={t("ontomap.register.hint")}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
      </div>
      <button className="btn" type="submit" disabled={register.isPending}>
        {t("ontomap.register.submit")}
      </button>
      {register.isSuccess && (
        <span className="text-xs text-green-700" role="status">
          {t("ontomap.register.done")}
        </span>
      )}
      <ErrorText error={register.error} />
    </form>
  );
}

function SessionTerms({
  tenantId,
  sessionId,
}: {
  tenantId: string;
  sessionId: string;
}) {
  const { t } = useTranslation();
  const { data } = useQuery({
    queryKey: ontoKeys(tenantId).candidates({ source_id: sessionId }),
    queryFn: () =>
      api<Page<OntoCandidate>>(ontoPath(tenantId, "/candidates"), {
        query: {
          source_type: "discovery_session",
          source_id: sessionId,
          limit: 200,
        },
      }),
  });
  if (!data?.items.length) return null;
  return (
    <section className="card space-y-1" data-testid="session-terms">
      <h3 className="font-medium">{t("ontomap.register.listed")}</h3>
      <div className="flex flex-wrap gap-1">
        {data.items.map((c) => (
          <span key={c.id} className="badge">
            {c.name} · {t(`candidateStatus.${c.status}`)}
          </span>
        ))}
      </div>
    </section>
  );
}

function QuestionCard({
  tenantId,
  sessionId,
  question,
  index,
  insights,
  department,
}: {
  tenantId: string;
  sessionId: string;
  question: SessionQuestion;
  index: number;
  insights: Worksheet["insights"];
  department: string | null;
}) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const [picked, setPicked] = useState("");
  const [answer, setAnswer] = useState(question.answer ?? "");
  const [insight, setInsight] = useState({ text: "", tags: "" });
  const save = useWorksheetMutation(
    tenantId,
    sessionId,
    `/session-questions/${question.id}`,
    "PATCH",
  );
  const remove = useWorksheetMutation(
    tenantId,
    sessionId,
    `/session-questions/${question.id}`,
    "DELETE",
  );
  const addInsight = useWorksheetMutation(
    tenantId,
    sessionId,
    `/sessions/${sessionId}/insights`,
  );
  const submitInsight = (e: FormEvent) => {
    e.preventDefault();
    addInsight.mutate(
      {
        text: insight.text,
        tags: splitTags(insight.tags),
        session_question_id: question.id,
      },
      { onSuccess: () => setInsight({ text: "", tags: "" }) },
    );
  };
  return (
    <li className="card space-y-2" data-testid="worksheet-question">
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-medium text-slate-800">
          {index}. {question.text}
        </h3>
        {canWrite && (
          <button
            className="btn btn-danger shrink-0"
            onClick={() => remove.mutate({})}
          >
            {t("common.delete")}
          </button>
        )}
      </div>
      {question.follow_ups.length > 0 && (
        <p className="text-xs text-slate-500">
          {t("discoveryq.followUps")}: {question.follow_ups.join(" / ")}
        </p>
      )}
      <Field label={t("discoveryq.field.answer")}>
        <textarea
          onSelect={(e) => {
            const el = e.currentTarget;
            const text = el.value.slice(el.selectionStart, el.selectionEnd);
            if (text.trim()) setPicked(text.trim());
          }}
          className="input"
          rows={3}
          readOnly={!canWrite}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          onBlur={() =>
            canWrite &&
            answer !== (question.answer ?? "") &&
            save.mutate({ answer: answer || null })
          }
        />
      </Field>
      {save.isSuccess && (
        <p className="text-xs text-green-700">
          {t("discoveryq.worksheet.saved")}
        </p>
      )}
      <ErrorText error={save.error ?? remove.error ?? addInsight.error} />
      {insights.length > 0 && (
        <ul className="space-y-1 text-sm">
          {insights.map((i) => (
            <li key={i.id} className="rounded bg-amber-50 px-2 py-1">
              {i.text} {i.tags.map((tag) => `#${tag}`).join(" ")}
            </li>
          ))}
        </ul>
      )}
      {canWrite && (
        <TermRegister
          key={picked}
          initial={picked}
          context={answer}
          tenantId={tenantId}
          sessionId={sessionId}
          questionId={question.id}
          department={department}
        />
      )}
      {canWrite && (
        <form className="flex items-end gap-2" onSubmit={submitInsight}>
          <div className="flex-1">
            <Field label={t("discoveryq.field.insight")}>
              <input
                className="input"
                required
                value={insight.text}
                onChange={(e) =>
                  setInsight({ ...insight, text: e.target.value })
                }
              />
            </Field>
          </div>
          <div className="w-40">
            <Field label={t("discoveryq.field.tags")}>
              <input
                className="input"
                value={insight.tags}
                onChange={(e) =>
                  setInsight({ ...insight, tags: e.target.value })
                }
              />
            </Field>
          </div>
          <button className="btn" type="submit">
            {t("discoveryq.worksheet.addInsight")}
          </button>
        </form>
      )}
    </li>
  );
}

function SessionMeta({ tenantId, ws }: { tenantId: string; ws: Worksheet }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const s = ws.session;
  const [summary, setSummary] = useState(s.summary ?? "");
  const patch = useWorksheetMutation(
    tenantId,
    s.id,
    `/sessions/${s.id}`,
    "PATCH",
  );
  return (
    <section className="card grid grid-cols-2 gap-3 md:grid-cols-4">
      <Field label={t("discoveryq.field.type")}>
        <StatusBadge group="sessionType" value={s.type} />
      </Field>
      <Field
        label={
          s.type === "coaching"
            ? t("discoveryq.field.mentee")
            : t("discoveryq.field.subject")
        }
      >
        <span className="text-sm">
          {ws.subject
            ? [ws.subject.name, ws.subject.department, ws.subject.job_title]
                .filter(Boolean)
                .join(" · ")
            : "—"}
        </span>
      </Field>
      <Field label={t("discoveryq.field.date")}>
        <input
          className="input"
          type="date"
          disabled={!canWrite}
          value={s.session_date ?? ""}
          onChange={(e) =>
            patch.mutate({ session_date: e.target.value || null })
          }
        />
      </Field>
      <Field label={t("common.status")}>
        {canWrite ? (
          <Select
            value={s.status}
            onChange={(v) => patch.mutate({ status: v })}
            options={SESSION_STATUSES}
            group="discoverySessionStatus"
          />
        ) : (
          <StatusBadge group="discoverySessionStatus" value={s.status} />
        )}
      </Field>
      <div className="col-span-full">
        <Field label={t("discoveryq.field.summary")}>
          <textarea
            className="input"
            rows={2}
            readOnly={!canWrite}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            onBlur={() =>
              canWrite &&
              summary !== (s.summary ?? "") &&
              patch.mutate({ summary: summary || null })
            }
          />
        </Field>
      </div>
      <ErrorText error={patch.error} />
    </section>
  );
}

function ActionForm({ tenantId, ws }: { tenantId: string; ws: Worksheet }) {
  const { t } = useTranslation();
  const empty = { title: "", assignee: "", due: "", insight_id: "" };
  const [form, setForm] = useState(empty);
  const create = useWorksheetMutation(
    tenantId,
    ws.session.id,
    `/sessions/${ws.session.id}/action-items`,
  );
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(
      {
        title: form.title,
        assignee: form.assignee || null,
        due: form.due || null,
        insight_id: form.insight_id || null,
      },
      { onSuccess: () => setForm(empty) },
    );
  };
  return (
    <form
      className="grid grid-cols-2 gap-3 md:grid-cols-5"
      onSubmit={submit}
      aria-label={t("discoveryq.worksheet.newAction")}
    >
      <Field label={t("discoveryq.field.action")}>
        <input
          className="input"
          required
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
        />
      </Field>
      <Field label={t("discoveryq.field.assignee")}>
        <input
          className="input"
          value={form.assignee}
          onChange={(e) => setForm({ ...form, assignee: e.target.value })}
        />
      </Field>
      <Field label={t("discoveryq.field.due")}>
        <input
          className="input"
          type="date"
          value={form.due}
          onChange={(e) => setForm({ ...form, due: e.target.value })}
        />
      </Field>
      <Field label={t("discoveryq.field.insight")}>
        <select
          className="input"
          value={form.insight_id}
          onChange={(e) => setForm({ ...form, insight_id: e.target.value })}
        >
          <option value="">{t("common.none")}</option>
          {ws.insights.map((i) => (
            <option key={i.id} value={i.id}>
              {i.text}
            </option>
          ))}
        </select>
      </Field>
      <div className="flex items-end gap-2">
        <button className="btn btn-primary" type="submit">
          {t("discoveryq.worksheet.addAction")}
        </button>
      </div>
      <div className="col-span-full">
        <ErrorText error={create.error} />
      </div>
    </form>
  );
}

export function WorksheetView({
  tenantId,
  sessionId,
  onBack,
}: {
  tenantId: string;
  sessionId: string;
  onBack: () => void;
}) {
  const { t, i18n } = useTranslation();
  const canWrite = useCanWrite();
  const role = useRole();
  const {
    data: ws,
    isLoading,
    error,
  } = useQuery({
    queryKey: discoveryKeys(tenantId).worksheet(sessionId),
    queryFn: () =>
      api<Worksheet>(discoveryPath(tenantId, `/sessions/${sessionId}`)),
  });
  const add = useWorksheetMutation(
    tenantId,
    sessionId,
    `/sessions/${sessionId}/questions`,
  );
  if (isLoading) return <Loading />;
  if (!ws) return <ErrorText error={error} />;
  const lang = i18n.language.startsWith("en") ? "en" : "ko";
  const byQuestion = (id: string) =>
    ws.insights.filter((i) => i.session_question_id === id);
  const unlinked = ws.insights.filter((i) => !i.session_question_id);
  return (
    <div className="space-y-4" data-testid="worksheet">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <button className="btn" onClick={onBack}>
            {t("discoveryq.worksheet.back")}
          </button>
          <h2 className="text-lg font-semibold text-slate-800">
            {ws.session.title}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {canWrite && ws.insights.length > 0 && (
            <Link
              className="btn"
              data-testid="send-flowdesk"
              to={handoffUrl("/flowdesk", {
                engagement: ws.session.engagement_id,
                insights: ws.insights.map((i) => i.id),
              })}
            >
              {t("handoff.toFlowDesk")}
            </Link>
          )}
          {canWrite && (
            <Link
              className="btn"
              data-testid="send-specforge"
              to={handoffUrl("/specforge", { engagement: ws.session.engagement_id, sessions: [sessionId] })}
            >
              {t("handoff.toSpecForge")}
            </Link>
          )}
        {role && AUDIT_ROLES.includes(role) && (
          <>
            <a
              className="btn"
              href={`/api/v1/t/${tenantId}/discoveryq/sessions/${sessionId}/export.md?lang=${lang}`}
            >
              {t("discoveryq.exportMd")}
            </a>
            <a
              className="btn"
              href={`/api/v1/t/${tenantId}/discoveryq/sessions/${sessionId}/report.docx?lang=${lang}`}
            >
              {t("discoveryq.reportDocx")}
            </a>
          </>
        )}
        </div>
      </div>
      <SessionMeta key={ws.session.updated_at} tenantId={tenantId} ws={ws} />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          {ws.questions.length === 0 ? (
            <div className="card">
              <Empty />
            </div>
          ) : (
            <ol className="space-y-3">
              {ws.questions.map((q, n) => (
                <QuestionCard
                  key={q.id}
                  tenantId={tenantId}
                  sessionId={sessionId}
                  question={q}
                  index={n + 1}
                  insights={byQuestion(q.id)}
                  department={ws.subject?.department ?? null}
                />
              ))}
            </ol>
          )}
          <SessionTerms tenantId={tenantId} sessionId={sessionId} />
          {unlinked.length > 0 && (
            <section className="card">
              <h3 className="mb-1 font-medium">
                {t("discoveryq.worksheet.otherInsights")}
              </h3>
              <ul className="space-y-1 text-sm">
                {unlinked.map((i) => (
                  <li key={i.id}>
                    {i.text} {i.tags.map((tag) => `#${tag}`).join(" ")}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
        {canWrite && (
          <div>
            <QuestionPicker
              tenantId={tenantId}
              session={ws.session}
              add={(body) => add.mutate(body)}
            />
            <ErrorText error={add.error} />
          </div>
        )}
      </div>
      <section
        className="card space-y-3"
        aria-label={t("discoveryq.tab.actions")}
      >
        <h2 className="font-semibold text-slate-800">
          {t("discoveryq.tab.actions")}
        </h2>
        {canWrite && <ActionForm tenantId={tenantId} ws={ws} />}
        {ws.action_items.length === 0 ? (
          <Empty />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("discoveryq.field.action")}</th>
                <th>{t("discoveryq.field.assignee")}</th>
                <th>{t("discoveryq.field.due")}</th>
                <th>{t("common.status")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {ws.action_items.map((a) => (
                <ActionItemRow key={a.id} tenantId={tenantId} item={a} />
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
