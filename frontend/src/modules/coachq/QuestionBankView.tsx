import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type { CustomQuestion } from "../../api/types";
import { Empty, ErrorText, Field, Loading } from "../../components/ui";
import { useCanWrite } from "../../app/hooks";
import { useWorkspace } from "../../app/store";
import { coachKeys, coachPath, useQuestionBank } from "./shared";

export function QuestionBankView({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const engagementId = useWorkspace((s) => s.engagementId);
  const qc = useQueryClient();
  const { data, isLoading } = useQuestionBank(tenantId);
  const [sessionType, setSessionType] = useState("");
  const [category, setCategory] = useState("");
  const [audience, setAudience] = useState("");
  const [q, setQ] = useState("");
  const [copied, setCopied] = useState<Set<string>>(new Set());
  const bank = data?.bank ?? null;
  const copy = useMutation({
    mutationFn: (questionId: string) =>
      api<CustomQuestion>(coachPath(tenantId, "/custom-questions"), {
        method: "POST",
        body: {
          engagement_id: engagementId,
          source_ref: {
            asset_id: bank?.asset_id,
            version: bank?.version,
            question_id: questionId,
          },
        },
      }),
    onSuccess: (_, questionId) => {
      setCopied((prev) => new Set(prev).add(questionId));
      void qc.invalidateQueries({ queryKey: coachKeys(tenantId).all });
    },
  });
  const categories = useMemo(() => {
    if (!bank) return [];
    const allowed = sessionType ? bank.session_types[sessionType] : undefined;
    const needle = q.trim().toLowerCase();
    return bank.categories
      .filter((c) => !allowed || allowed.includes(c.key))
      .filter((c) => !category || c.key === category)
      .map((c) => ({
        ...c,
        questions: c.questions.filter(
          (x) =>
            (!audience || x.audience.includes(audience)) &&
            (!needle ||
              x.text.toLowerCase().includes(needle) ||
              x.tags.some((tag) => tag.toLowerCase().includes(needle))),
        ),
      }))
      .filter((c) => c.questions.length > 0);
  }, [bank, sessionType, category, audience, q]);

  if (isLoading) return <Loading />;
  if (!bank)
    return (
      <p className="card text-sm text-slate-600">{t("coachq.bank.missing")}</p>
    );
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">
        {bank.title} · v{bank.version}
      </p>
      <div className="card grid grid-cols-2 gap-3 md:grid-cols-4">
        <Field label={t("coachq.field.type")}>
          <select
            className="input"
            value={sessionType}
            onChange={(e) => setSessionType(e.target.value)}
          >
            <option value="">{t("common.all")}</option>
            {Object.keys(bank.session_types).map((x) => (
              <option key={x} value={x}>
                {t(`sessionType.${x}`, { defaultValue: x })}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("coachq.field.category")}>
          <select
            className="input"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">{t("common.all")}</option>
            {bank.categories.map((c) => (
              <option key={c.key} value={c.key}>
                {c.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("coachq.field.audience")}>
          <select
            className="input"
            value={audience}
            onChange={(e) => setAudience(e.target.value)}
          >
            <option value="">{t("common.all")}</option>
            {bank.audiences.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("common.search")}>
          <input
            className="input"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </Field>
      </div>
      <ErrorText error={copy.error} />
      {categories.length === 0 && <Empty />}
      {categories.map((c) => (
        <section key={c.key} className="card" data-testid={`bank-${c.key}`}>
          <h2 className="mb-2 font-semibold text-slate-800">
            {c.name}{" "}
            <span className="text-xs text-slate-500">
              ({c.questions.length})
            </span>
          </h2>
          <ul className="divide-y divide-slate-100">
            {c.questions.map((x) => (
              <li
                key={x.id}
                className="flex items-start justify-between gap-3 py-2"
              >
                <div>
                  <p className="text-sm text-slate-800">{x.text}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {x.audience.join(", ")}
                    {x.tags.length > 0 &&
                      ` · ${x.tags.map((tag) => `#${tag}`).join(" ")}`}
                  </p>
                  {x.follow_ups.length > 0 && (
                    <p className="mt-1 text-xs text-slate-500">
                      {t("coachq.followUps")}: {x.follow_ups.join(" / ")}
                    </p>
                  )}
                </div>
                {canWrite && (
                  <button
                    className="btn shrink-0"
                    disabled={copied.has(x.id) || copy.isPending}
                    onClick={() => copy.mutate(x.id)}
                  >
                    {copied.has(x.id)
                      ? t("coachq.bank.copied")
                      : t("coachq.bank.copy")}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
