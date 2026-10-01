import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, tenantPath } from "../../api/client";
import type { InterfaceUpload } from "../../api/types";
import { ErrorText, StatusBadge } from "../../components/ui";
import { ifKeys } from "./shared";

export function UploadPanel({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [upload, setUpload] = useState<InterfaceUpload | null>(null);
  const [register, setRegister] = useState<Set<string>>(new Set());
  const send = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api<InterfaceUpload>(tenantPath(tenantId, "/interfaces/uploads"), {
        method: "POST",
        body: form,
      });
    },
    onSuccess: (u) => {
      setUpload(u);
      setRegister(new Set(u.result.unregistered_systems.map((s) => s.name)));
    },
  });
  const apply = useMutation({
    mutationFn: (id: string) =>
      api<InterfaceUpload>(
        tenantPath(tenantId, `/interfaces/uploads/${id}/apply`),
        {
          method: "POST",
          body: { register_systems: [...register] },
        },
      ),
    onSuccess: (u) => {
      setUpload(u);
      void qc.invalidateQueries({ queryKey: ifKeys(tenantId).all });
      void qc.invalidateQueries({ queryKey: ["systems", tenantId] });
    },
  });
  const toggle = (name: string) =>
    setRegister((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  const result = upload?.result;
  const applied = result?.applied;
  return (
    <div className="space-y-4">
      <div className="card flex items-center gap-3">
        <input
          ref={input}
          type="file"
          accept=".xlsx,.xlsm"
          aria-label={t("interfaces.upload.file")}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) send.mutate(f);
            e.target.value = "";
          }}
        />
        <p className="text-sm text-slate-500">{t("interfaces.upload.hint")}</p>
        <ErrorText error={send.error} />
      </div>
      {result && upload && (
        <>
          <div
            className="card grid grid-cols-5 gap-3 text-center"
            data-testid="upload-summary"
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
          {result.unregistered_systems.length > 0 &&
            upload.status === "validated" && (
              <div
                className="card space-y-2"
                data-testid="unregistered-systems"
              >
                <h2 className="font-semibold">
                  {t("interfaces.upload.unregistered")}
                </h2>
                <p className="text-sm text-slate-500">
                  {t("interfaces.upload.unregisteredHint")}
                </p>
                {result.unregistered_systems.map((s) => (
                  <label
                    key={s.name}
                    className="flex items-center gap-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={register.has(s.name)}
                      onChange={() => toggle(s.name)}
                    />
                    <span className="font-medium">{s.name}</span>
                    <span className="text-slate-500">
                      {t("interfaces.upload.rowCount", { count: s.rows })}
                      {s.in_system_sheet &&
                        ` · ${t("interfaces.upload.inSheet")}`}
                    </span>
                  </label>
                ))}
              </div>
            )}
          <div className="card">
            <table className="table" data-testid="upload-rows">
              <thead>
                <tr>
                  <th>{t("interfaces.upload.row")}</th>
                  <th>{t("ifField.if_code")}</th>
                  <th>{t("ifField.name")}</th>
                  <th>{t("ifField.source")}</th>
                  <th>{t("ifField.target")}</th>
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
                    <td className="font-mono text-xs">{r.values.if_code}</td>
                    <td>{r.values.name}</td>
                    <td>{r.values.source}</td>
                    <td>{r.values.target}</td>
                    <td>
                      <StatusBadge
                        group="interfaces.upload.actions"
                        value={r.action}
                      />
                    </td>
                    <td className="text-xs text-red-700">
                      {r.errors
                        .map(
                          (e) =>
                            `${t(`ifField.${e.field}`)}: ${t(`interfaces.upload.err.${e.code}`)}`,
                        )
                        .join(", ")}
                      {r.unregistered.length > 0 && (
                        <span className="text-amber-700">
                          {r.errors.length > 0 && ", "}
                          {t("interfaces.upload.missingSystems", {
                            names: r.unregistered.join(", "),
                          })}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {upload.status === "validated" ? (
            <div className="flex items-center gap-3">
              <button
                className="btn btn-primary"
                onClick={() => apply.mutate(upload.id)}
                disabled={apply.isPending}
              >
                {t("interfaces.upload.apply")}
              </button>
              <ErrorText error={apply.error} />
            </div>
          ) : (
            applied && (
              <div
                className="card text-sm"
                role="status"
                data-testid="upload-applied"
              >
                {t("interfaces.upload.appliedSummary", {
                  created: applied.created,
                  updated: applied.updated,
                  skipped: applied.skipped.length,
                  systems: applied.systems_created.length,
                })}
              </div>
            )
          )}
        </>
      )}
    </div>
  );
}
