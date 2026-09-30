import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { api, tenantPath } from "../api/client";
import type { Page, StoredFile } from "../api/types";
import { Empty, ErrorText, NeedTenant, PageHeader } from "../components/ui";
import { useCanWrite, useTenantId } from "../app/hooks";
import { fmtDate } from "../app/format";

export function FilesPage() {
  const { t } = useTranslation();
  const tenantId = useTenantId();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const key = ["files", tenantId];
  const { data } = useQuery({
    queryKey: key,
    queryFn: () => api<Page<StoredFile>>(tenantPath(tenantId, "/files"), { query: { limit: 200 } }),
    enabled: !!tenantId,
  });
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api<StoredFile>(tenantPath(tenantId, "/files"), { method: "POST", body: form });
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: key }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api<unknown>(tenantPath(tenantId, `/files/${id}`), { method: "DELETE" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: key }),
  });
  if (!tenantId) return <NeedTenant />;
  return (
    <div className="space-y-4">
      <PageHeader
        title={t("nav.files")}
        actions={
          canWrite && (
            <>
              <input
                ref={input}
                type="file"
                className="hidden"
                aria-label={t("files.upload")}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) upload.mutate(f);
                  e.target.value = "";
                }}
              />
              <button className="btn btn-primary" onClick={() => input.current?.click()}>
                {t("files.upload")}
              </button>
            </>
          )
        }
      />
      <ErrorText error={upload.error} />
      <div className="card">
        {!data?.items.length ? (
          <Empty />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("files.filename")}</th>
                <th>{t("files.size")}</th>
                <th>{t("common.createdAt")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((f) => (
                <tr key={f.id}>
                  <td>
                    <a className="text-blue-700 hover:underline" href={`/api/v1/t/${tenantId}/files/${f.id}/download`}>
                      {f.filename}
                    </a>
                  </td>
                  <td>{f.size.toLocaleString()} B</td>
                  <td>{fmtDate(f.created_at)}</td>
                  <td className="text-right">
                    {canWrite && (
                      <button className="btn btn-danger" onClick={() => remove.mutate(f.id)}>
                        {t("common.delete")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
