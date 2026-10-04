import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type { CustomQuestion } from "../../api/types";
import { Empty, ErrorText, Field } from "../../components/ui";
import { useCanWrite } from "../../app/hooks";
import { useWorkspace } from "../../app/store";
import {
  discoveryKeys,
  discoveryPath,
  splitTags,
  useCustomQuestions,
  useQuestionBank,
} from "./shared";

function QuestionEditor({
  tenantId,
  question,
  onDone,
}: {
  tenantId: string;
  question: CustomQuestion | null;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const engagementId = useWorkspace((s) => s.engagementId);
  const categories = useQuestionBank(tenantId).data?.bank?.categories ?? [];
  const qc = useQueryClient();
  const [form, setForm] = useState({
    text: question?.text ?? "",
    category: question?.category ?? "",
    tags: question?.tags.join(", ") ?? "",
    follow_ups: question?.follow_ups.join("\n") ?? "",
  });
  const save = useMutation({
    mutationFn: () => {
      const body = {
        text: form.text,
        category: form.category || null,
        tags: splitTags(form.tags),
        follow_ups: form.follow_ups
          .split("\n")
          .map((x) => x.trim())
          .filter(Boolean),
      };
      return question
        ? api<CustomQuestion>(
            discoveryPath(tenantId, `/custom-questions/${question.id}`),
            { method: "PATCH", body },
          )
        : api<CustomQuestion>(discoveryPath(tenantId, "/custom-questions"), {
            method: "POST",
            body: { ...body, engagement_id: engagementId },
          });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: discoveryKeys(tenantId).all });
      setForm({ text: "", category: "", tags: "", follow_ups: "" });
      onDone();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };
  return (
    <form
      className="card grid grid-cols-1 gap-3 md:grid-cols-4"
      onSubmit={submit}
      aria-label={
        question ? t("discoveryq.custom.edit") : t("discoveryq.custom.new")
      }
    >
      <div className="md:col-span-2">
        <Field label={t("discoveryq.field.question")}>
          <textarea
            className="input"
            required
            rows={2}
            value={form.text}
            onChange={(e) => setForm({ ...form, text: e.target.value })}
          />
        </Field>
      </div>
      <Field label={t("discoveryq.field.category")}>
        <select
          className="input"
          value={form.category}
          onChange={(e) => setForm({ ...form, category: e.target.value })}
        >
          <option value="">{t("common.none")}</option>
          {categories.map((c) => (
            <option key={c.key} value={c.key}>
              {c.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("discoveryq.field.tags")}>
        <input
          className="input"
          value={form.tags}
          onChange={(e) => setForm({ ...form, tags: e.target.value })}
        />
      </Field>
      <div className="md:col-span-4">
        <Field label={t("discoveryq.followUps")}>
          <textarea
            className="input"
            rows={2}
            value={form.follow_ups}
            onChange={(e) => setForm({ ...form, follow_ups: e.target.value })}
          />
        </Field>
      </div>
      <div className="col-span-full flex items-center gap-2">
        <button className="btn btn-primary" type="submit">
          {question ? t("common.save") : t("common.create")}
        </button>
        {question && (
          <button className="btn" type="button" onClick={onDone}>
            {t("common.cancel")}
          </button>
        )}
        <ErrorText error={save.error} />
      </div>
    </form>
  );
}

export function CustomQuestionsView({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const engagementId = useWorkspace((s) => s.engagementId);
  const qc = useQueryClient();
  const { data } = useCustomQuestions(tenantId, engagementId);
  const categories = useQuestionBank(tenantId).data?.bank?.categories ?? [];
  const catName = new Map(categories.map((c) => [c.key, c.name]));
  const [editing, setEditing] = useState<CustomQuestion | null>(null);
  const remove = useMutation({
    mutationFn: (id: string) =>
      api(discoveryPath(tenantId, `/custom-questions/${id}`), {
        method: "DELETE",
      }),
    onSuccess: () =>
      void qc.invalidateQueries({ queryKey: discoveryKeys(tenantId).all }),
  });
  return (
    <div className="space-y-3">
      {canWrite && (
        <QuestionEditor
          key={editing?.id ?? "new"}
          tenantId={tenantId}
          question={editing}
          onDone={() => setEditing(null)}
        />
      )}
      <div className="card">
        {!data?.items.length ? (
          <Empty />
        ) : (
          <table className="table" data-testid="custom-question-table">
            <thead>
              <tr>
                <th>{t("discoveryq.field.question")}</th>
                <th>{t("discoveryq.field.category")}</th>
                <th>{t("discoveryq.field.tags")}</th>
                <th>{t("discoveryq.custom.source")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((q) => (
                <tr key={q.id}>
                  <td>{q.text}</td>
                  <td>
                    {q.category ? (catName.get(q.category) ?? q.category) : ""}
                  </td>
                  <td>{q.tags.map((x) => `#${x}`).join(" ")}</td>
                  <td className="font-mono text-xs">
                    {q.source_ref?.question_id ?? t("discoveryq.custom.own")}
                  </td>
                  <td className="space-x-1 text-right whitespace-nowrap">
                    {canWrite && (
                      <>
                        <button className="btn" onClick={() => setEditing(q)}>
                          {t("common.edit")}
                        </button>
                        <button
                          className="btn btn-danger"
                          onClick={() => remove.mutate(q.id)}
                        >
                          {t("common.delete")}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <ErrorText error={remove.error} />
      </div>
    </div>
  );
}
