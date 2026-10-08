import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type { SpecDiff, SpecDocument, SpecVersion } from "../../api/types";
import { fmtDate } from "../../app/format";
import { AUDIT_ROLES, useCanWrite, useRole } from "../../app/hooks";
import { Empty, ErrorText, Field, Loading, StatusBadge } from "../../components/ui";
import { DiffView } from "../../core/AssetsPage";
import { Markdown } from "../../manual/markdown";
import { specKeys, specPath } from "./shared";

export function SpecEditor({ tenantId, docId, onBack }: { tenantId: string; docId: string; onBack: () => void }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const role = useRole();
  const canExport = role !== undefined && AUDIT_ROLES.includes(role);
  const qc = useQueryClient();
  const keys = specKeys(tenantId);
  const url = specPath(tenantId, `/documents/${docId}`);
  const {
    data: doc,
    isLoading,
    error,
  } = useQuery({
    queryKey: keys.doc(docId),
    queryFn: () => api<SpecDocument>(url),
  });
  const [edited, setEdited] = useState<string | null>(null);
  const refresh = (d: SpecDocument) => {
    qc.setQueryData(keys.doc(docId), d);
    void qc.invalidateQueries({ queryKey: keys.all });
  };
  const patch = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<SpecDocument>(url, { method: "PATCH", body }),
    onSuccess: (d) => {
      setEdited(null);
      refresh(d);
    },
  });
  const reassemble = useMutation({
    mutationFn: () => api<SpecDocument>(`${url}/assemble`, { method: "POST" }),
    onSuccess: (d) => {
      setEdited(null);
      refresh(d);
    },
  });
  const remove = useMutation({
    mutationFn: () => api<unknown>(url, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.all });
      onBack();
    },
  });
  if (isLoading) return <Loading />;
  if (!doc) return <ErrorText error={error} />;
  const content = edited ?? doc.content_md;
  const dirty = edited !== null;
  const confirmed = doc.status === "confirmed";
  return (
    <div className="space-y-4" data-testid="spec-editor">
      <div className="card flex flex-wrap items-center gap-3">
        <button type="button" className="btn" onClick={onBack}>
          {t("specforge.back")}
        </button>
        <h2 className="text-lg font-semibold" data-testid="spec-title">
          {doc.title}
        </h2>
        <span className="badge">{t(`specDocType.${doc.doc_type}`)}</span>
        <StatusBadge group="specStatus" value={doc.status} />
        <div className="ml-auto flex flex-wrap gap-2">
          {canWrite && (
            <>
              <button
                type="button"
                className="btn btn-primary"
                disabled={!dirty || patch.isPending}
                onClick={() => patch.mutate({ content_md: content })}
              >
                {t("common.save")}
              </button>
              <button
                type="button"
                className="btn"
                disabled={reassemble.isPending}
                onClick={() => window.confirm(t("specforge.confirmReassemble")) && reassemble.mutate()}
              >
                {t("specforge.reassemble")}
              </button>
              <button
                type="button"
                className="btn"
                disabled={dirty || patch.isPending}
                onClick={() => patch.mutate({ status: confirmed ? "draft" : "confirmed" })}
              >
                {confirmed ? t("specforge.reopen") : t("specforge.confirm")}
              </button>
            </>
          )}
          {canExport && (
            <a className="btn" href={`/api/v1${url}/export.md`} data-testid="spec-export-md">
              {t("specforge.exportMd", { name: doc.doc_type === "spec" ? "Spec.md" : "Devin.md" })}
            </a>
          )}
          {canWrite && (
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => window.confirm(t("specforge.confirmDelete")) && remove.mutate()}
            >
              {t("common.delete")}
            </button>
          )}
        </div>
        {dirty && <span className="text-sm text-amber-700">{t("specforge.unsaved")}</span>}
        <ErrorText error={patch.error ?? reassemble.error ?? remove.error} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card">
          <h3 className="mb-2 font-semibold">{t("specforge.editor")}</h3>
          <textarea
            className="input h-[32rem] w-full font-mono text-xs"
            value={content}
            readOnly={!canWrite}
            onChange={(e) => setEdited(e.target.value)}
            aria-label={t("specforge.editor")}
            data-testid="spec-content"
          />
        </div>
        <div className="card max-h-[36rem] overflow-auto" data-testid="spec-preview">
          <h3 className="mb-2 font-semibold">{t("specforge.preview")}</h3>
          <Markdown source={content} />
        </div>
      </div>
      {canWrite && <EnrichPanel url={url} dirty={dirty} onApply={(text) => setEdited(text)} />}
      <VersionsPanel tenantId={tenantId} docId={docId} dirty={dirty} canWrite={canWrite} onRestored={refresh} />
    </div>
  );
}

function EnrichPanel({ url, dirty, onApply }: { url: string; dirty: boolean; onApply: (text: string) => void }) {
  const { t } = useTranslation();
  const [instructions, setInstructions] = useState("");
  const [pasted, setPasted] = useState("");
  const [copied, setCopied] = useState(false);
  const body = { instructions: instructions || null };
  const prompt = useMutation({
    mutationFn: () => api<{ prompt: string; llm_available: boolean }>(`${url}/enrich-prompt`, { method: "POST", body }),
  });
  const llm = useMutation({
    mutationFn: () => api<{ content_md: string }>(`${url}/enrich`, { method: "POST", body }),
    onSuccess: (r) => onApply(r.content_md),
  });
  const copy = (text: string) => {
    void navigator.clipboard?.writeText(text).then(() => setCopied(true));
  };
  return (
    <div className="card space-y-3" data-testid="spec-enrich">
      <h3 className="font-semibold">{t("specforge.enrich")}</h3>
      <p className="text-sm text-slate-600">{t("specforge.enrichHint")}</p>
      {dirty && <p className="text-sm text-amber-700">{t("specforge.saveBeforeEnrich")}</p>}
      <Field label={t("specforge.instructions")}>
        <input className="input w-full" value={instructions} onChange={(e) => setInstructions(e.target.value)} />
      </Field>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn" disabled={dirty || prompt.isPending} onClick={() => prompt.mutate()}>
          {t("specforge.makePrompt")}
        </button>
        {prompt.data?.llm_available && (
          <button
            type="button"
            className="btn btn-primary"
            disabled={dirty || llm.isPending}
            onClick={() => llm.mutate()}
          >
            {llm.isPending ? t("common.loading") : t("specforge.enrichLlm")}
          </button>
        )}
      </div>
      <ErrorText error={prompt.error ?? llm.error} />
      {prompt.data && (
        <div className="grid gap-3 lg:grid-cols-2">
          <div>
            <div className="mb-1 flex items-center gap-2">
              <span className="text-sm font-medium">{t("specforge.prompt")}</span>
              <button type="button" className="btn" onClick={() => copy(prompt.data.prompt)}>
                {copied ? t("specforge.copied") : t("specforge.copy")}
              </button>
            </div>
            <textarea
              className="input h-48 w-full font-mono text-xs"
              readOnly
              value={prompt.data.prompt}
              data-testid="spec-prompt"
            />
          </div>
          <div>
            <div className="mb-1 flex items-center gap-2">
              <span className="text-sm font-medium">{t("specforge.pasteResult")}</span>
              <button
                type="button"
                className="btn"
                disabled={!pasted.trim()}
                onClick={() => {
                  onApply(pasted.trim() + "\n");
                  setPasted("");
                }}
              >
                {t("specforge.apply")}
              </button>
            </div>
            <textarea
              className="input h-48 w-full font-mono text-xs"
              value={pasted}
              onChange={(e) => setPasted(e.target.value)}
              aria-label={t("specforge.pasteResult")}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function VersionsPanel({
  tenantId,
  docId,
  dirty,
  canWrite,
  onRestored,
}: {
  tenantId: string;
  docId: string;
  dirty: boolean;
  canWrite: boolean;
  onRestored: (d: SpecDocument) => void;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const keys = specKeys(tenantId);
  const url = specPath(tenantId, `/documents/${docId}`);
  const [note, setNote] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const { data: versions, isLoading } = useQuery({
    queryKey: keys.versions(docId),
    queryFn: () => api<SpecVersion[]>(`${url}/versions`),
  });
  const reload = () => {
    void qc.invalidateQueries({ queryKey: keys.versions(docId) });
    void qc.invalidateQueries({ queryKey: keys.all });
  };
  const save = useMutation({
    mutationFn: () => api<SpecVersion>(`${url}/versions`, { method: "POST", body: { note: note || null } }),
    onSuccess: () => {
      setNote("");
      reload();
    },
  });
  const restore = useMutation({
    mutationFn: (id: string) => api<SpecDocument>(`${url}/versions/${id}/restore`, { method: "POST" }),
    onSuccess: (d) => {
      onRestored(d);
      reload();
    },
  });
  const latest = versions?.[0]?.version;
  const fromVersion = from || (latest !== undefined ? String(latest) : "");
  const diff = useQuery({
    queryKey: ["specforge", tenantId, "diff", docId, fromVersion, to, versions?.length],
    enabled: !!fromVersion,
    queryFn: () => api<SpecDiff>(`${url}/diff`, { query: { from_version: fromVersion, to_version: to || undefined } }),
  });
  const items = versions ?? [];
  return (
    <div className="card space-y-3" data-testid="spec-versions">
      <h3 className="font-semibold">{t("specforge.versions")}</h3>
      {canWrite && (
        <div className="flex flex-wrap items-end gap-2">
          <Field label={t("specforge.versionNote")}>
            <input className="input" value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} />
          </Field>
          <button type="button" className="btn" disabled={dirty || save.isPending} onClick={() => save.mutate()}>
            {t("specforge.saveVersion")}
          </button>
          {dirty && <span className="text-sm text-amber-700">{t("specforge.saveFirst")}</span>}
        </div>
      )}
      <ErrorText error={save.error ?? restore.error} />
      {isLoading ? (
        <Loading />
      ) : items.length === 0 ? (
        <Empty />
      ) : (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>{t("specforge.field.version")}</th>
                <th>{t("specforge.versionNote")}</th>
                <th>{t("common.createdAt")}</th>
                {canWrite && <th />}
              </tr>
            </thead>
            <tbody>
              {items.map((v) => (
                <tr key={v.id}>
                  <td>v{v.version}</td>
                  <td>{v.note}</td>
                  <td>{fmtDate(v.created_at)}</td>
                  {canWrite && (
                    <td>
                      <button
                        type="button"
                        className="btn"
                        onClick={() => window.confirm(t("specforge.confirmRestore")) && restore.mutate(v.id)}
                      >
                        {t("specforge.restore")}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex flex-wrap items-end gap-2">
            <Field label={t("specforge.diffFrom")}>
              <select
                className="input"
                value={fromVersion}
                onChange={(e) => setFrom(e.target.value)}
                aria-label={t("specforge.diffFrom")}
              >
                {items.map((v) => (
                  <option key={v.id} value={v.version}>
                    v{v.version}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("specforge.diffTo")}>
              <select
                className="input"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                aria-label={t("specforge.diffTo")}
              >
                <option value="">{t("specforge.working")}</option>
                {items.map((v) => (
                  <option key={v.id} value={v.version}>
                    v{v.version}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          {diff.data &&
            (diff.data.diff ? (
              <div data-testid="spec-diff">
                <DiffView text={diff.data.diff} />
              </div>
            ) : (
              <p className="text-sm text-slate-500" data-testid="spec-diff">
                {t("specforge.noDiff")}
              </p>
            ))}
        </>
      )}
    </div>
  );
}
