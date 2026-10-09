import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type { Flow, FlowGeneratePrompt, FlowInsightOption } from "../../api/types";
import { ErrorText, Field, Select } from "../../components/ui";
import { FLOW_KINDS, PERSPECTIVES, flowKeys, flowPath } from "./shared";

export function GenerateFlow({
  tenantId,
  engagementId,
  initialInsights = [],
  onCreated,
}: {
  tenantId: string;
  engagementId: string;
  initialInsights?: string[];
  onCreated: (f: Flow) => void;
}) {
  const { t, i18n } = useTranslation();
  const [form, setForm] = useState({ title: "", kind: "as_is", perspective: "business", description: "" });
  const [picked, setPicked] = useState<string[]>(initialInsights);
  const [answer, setAnswer] = useState("");
  const [copied, setCopied] = useState(false);
  const insights = useQuery({
    queryKey: [...flowKeys(tenantId).all, "insights", engagementId],
    queryFn: () =>
      api<FlowInsightOption[]>(flowPath(tenantId, "/insights"), { query: { engagement_id: engagementId } }),
    enabled: !!engagementId,
  });
  const body = () => ({
    engagement_id: engagementId,
    ...form,
    insight_ids: picked,
    lang: i18n.language.startsWith("en") ? "en" : "ko",
  });
  const prompt = useMutation({
    mutationFn: () => api<FlowGeneratePrompt>(flowPath(tenantId, "/generate/prompt"), { method: "POST", body: body() }),
    onSuccess: () => setCopied(false),
  });
  const generate = useMutation({
    mutationFn: (pasted: string | null) =>
      api<Flow>(flowPath(tenantId, "/generate"), { method: "POST", body: { ...body(), answer: pasted } }),
    onSuccess: onCreated,
  });
  const set = (k: keyof typeof form) => (v: string) => {
    setForm((f) => ({ ...f, [k]: v }));
    prompt.reset();
  };
  const toggle = (id: string) => {
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
    prompt.reset();
  };
  const ready = !!engagementId && !!form.title.trim() && (!!form.description.trim() || picked.length > 0);
  const options = insights.data ?? [];
  const copy = async () => {
    if (!prompt.data) return;
    await navigator.clipboard.writeText(prompt.data.prompt);
    setCopied(true);
  };
  return (
    <section className="card space-y-3" aria-label={t("flowdesk.gen.title")}>
      <h2 className="font-semibold">{t("flowdesk.gen.title")}</h2>
      <p className="text-sm text-slate-600">{t("flowdesk.gen.intro")}</p>
      <div className="grid gap-3 md:grid-cols-3">
        <Field label={t("flowdesk.field.title")}>
          <input className="input" value={form.title} onChange={(e) => set("title")(e.target.value)} />
        </Field>
        <Field label={t("flowdesk.field.kind")}>
          <Select value={form.kind} onChange={set("kind")} options={FLOW_KINDS} group="flowKind" />
        </Field>
        <Field label={t("flowdesk.field.perspective")}>
          <Select value={form.perspective} onChange={set("perspective")} options={PERSPECTIVES} group="perspective" />
        </Field>
      </div>
      <Field label={t("flowdesk.gen.description")}>
        <textarea
          className="input min-h-24"
          value={form.description}
          placeholder={t("flowdesk.gen.descriptionHint")}
          onChange={(e) => set("description")(e.target.value)}
        />
      </Field>
      <div>
        <span className="label">{t("flowdesk.gen.insights")}</span>
        {options.length === 0 ? (
          <p className="text-sm text-slate-500">{t("flowdesk.gen.noInsights")}</p>
        ) : (
          <ul className="max-h-48 space-y-1 overflow-auto rounded border p-2 text-sm" data-testid="gen-insights">
            {options.map((x) => (
              <li key={x.id}>
                <label className="flex items-start gap-2">
                  <input type="checkbox" checked={picked.includes(x.id)} onChange={() => toggle(x.id)} />
                  <span>
                    <span className="text-slate-500">[{x.session_title}]</span> {x.text}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex flex-wrap gap-3">
        <button className="btn" type="button" disabled={!ready || prompt.isPending} onClick={() => prompt.mutate()}>
          {t("flowdesk.gen.makePrompt")}
        </button>
        {prompt.data?.llm_available && (
          <button
            className="btn btn-primary"
            type="button"
            disabled={!ready || generate.isPending}
            onClick={() => generate.mutate(null)}
          >
            {generate.isPending ? t("flowdesk.gen.running") : t("flowdesk.gen.runLlm")}
          </button>
        )}
      </div>
      {prompt.data && (
        <div className="space-y-3">
          <Field label={t("flowdesk.gen.prompt")}>
            <textarea className="input min-h-40 font-mono text-xs" readOnly value={prompt.data.prompt} />
          </Field>
          <button className="btn" type="button" onClick={() => void copy()}>
            {copied ? t("flowdesk.gen.copied") : t("flowdesk.gen.copy")}
          </button>
          <Field label={t("flowdesk.gen.answer")}>
            <textarea
              className="input min-h-32 font-mono text-xs"
              value={answer}
              placeholder={t("flowdesk.gen.answerHint")}
              onChange={(e) => setAnswer(e.target.value)}
            />
          </Field>
          <button
            className="btn btn-primary"
            type="button"
            disabled={!answer.trim() || generate.isPending}
            onClick={() => generate.mutate(answer)}
          >
            {t("flowdesk.gen.fromAnswer")}
          </button>
        </div>
      )}
      <ErrorText error={prompt.error ?? generate.error} />
    </section>
  );
}
