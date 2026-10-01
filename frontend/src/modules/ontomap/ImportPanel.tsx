import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type { GlossaryImportResult } from "../../api/types";
import { ErrorText, StatusBadge } from "../../components/ui";
import { formatAliases, ontoKeys, ontoPath } from "./shared";

export function ImportPanel({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<GlossaryImportResult | null>(null);
  const send = useMutation({
    mutationFn: ({ f, apply }: { f: File; apply: boolean }) => {
      const form = new FormData();
      form.append("file", f);
      return api<GlossaryImportResult>(ontoPath(tenantId, "/terms/import"), {
        method: "POST",
        body: form,
        query: { apply },
      });
    },
    onSuccess: (r) => {
      setResult(r);
      if (r.applied)
        void qc.invalidateQueries({ queryKey: ontoKeys(tenantId).all });
    },
  });
  return (
    <div className="space-y-4">
      <div className="card flex items-center gap-3">
        <input
          type="file"
          accept=".xlsx,.xlsm"
          aria-label={t("ontomap.import.file")}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) {
              setFile(f);
              send.mutate({ f, apply: false });
            }
            e.target.value = "";
          }}
        />
        <p className="text-sm text-slate-500">{t("ontomap.import.hint")}</p>
        <ErrorText error={send.error} />
      </div>
      {result && (
        <>
          <div
            className="card grid grid-cols-5 gap-3 text-center"
            data-testid="glossary-import-summary"
          >
            {(["total", "valid", "invalid", "create", "update"] as const).map(
              (k) => (
                <div key={k}>
                  <div className="text-xs text-slate-500">
                    {t(`interfaces.upload.summary.${k}`)}
                  </div>
                  <div className="text-xl font-semibold">
                    {result.summary[k]}
                  </div>
                </div>
              ),
            )}
          </div>
          <div className="card">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("interfaces.upload.row")}</th>
                  <th>{t("ontomap.field.term")}</th>
                  <th>{t("ontomap.field.definition")}</th>
                  <th>{t("ontomap.field.aliases")}</th>
                  <th>{t("interfaces.upload.action")}</th>
                  <th>{t("interfaces.upload.problems")}</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((r) => (
                  <tr
                    key={r.row}
                    className={r.errors.length ? "bg-red-50" : undefined}
                  >
                    <td>{r.row}</td>
                    <td>{r.values.term}</td>
                    <td>{r.values.definition}</td>
                    <td>{formatAliases(r.values.aliases)}</td>
                    <td>
                      <StatusBadge
                        group="ontomap.import.actions"
                        value={r.action}
                      />
                    </td>
                    <td className="text-xs text-red-700">
                      {r.errors
                        .map(
                          (e) =>
                            `${t(`ontomap.field.${e.field}`)}: ${t(`ontomap.import.err.${e.code}`)}`,
                        )
                        .join(", ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.applied ? (
            <div className="card text-sm" role="status">
              {t("ontomap.import.applied", {
                created: result.summary.create,
                updated: result.summary.update,
                skipped: result.summary.invalid,
              })}
            </div>
          ) : (
            file && (
              <button
                className="btn btn-primary"
                disabled={send.isPending || result.summary.valid === 0}
                onClick={() => send.mutate({ f: file, apply: true })}
              >
                {t("interfaces.upload.apply")}
              </button>
            )
          )}
        </>
      )}
    </div>
  );
}
