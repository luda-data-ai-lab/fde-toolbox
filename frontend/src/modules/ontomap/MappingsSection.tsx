import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type {
  MappingKind,
  MappingSources,
  OntoConceptDetail,
  OntoMapping,
} from "../../api/types";
import { ErrorText, Field, Select } from "../../components/ui";
import { useCanWrite } from "../../app/hooks";
import { MAPPING_ORIGINS, ontoKeys, ontoPath } from "./shared";

const EMPTY = {
  target: "",
  system_id: "",
  table_name: "",
  column_name: "",
  interface_id: "",
  origin: "manual",
};

export function MappingsSection({
  tenantId,
  concept,
}: {
  tenantId: string;
  concept: OntoConceptDetail;
}) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const keys = ontoKeys(tenantId);
  const { data: sources } = useQuery({
    queryKey: keys.sources,
    queryFn: () => api<MappingSources>(ontoPath(tenantId, "/mapping-sources")),
  });
  const [form, setForm] = useState({
    ...EMPTY,
    target: `concept:${concept.id}`,
  });
  const refresh = () => void qc.invalidateQueries({ queryKey: keys.all });
  const add = useMutation({
    mutationFn: () => {
      const [kind = "concept", ...rest] = form.target.split(":");
      return api<OntoMapping>(ontoPath(tenantId, "/mappings"), {
        method: "POST",
        body: {
          target_kind: kind,
          target_id: rest.join(":"),
          system_id: form.system_id || null,
          table_name: form.table_name || null,
          column_name: form.column_name || null,
          interface_id: form.interface_id || null,
          origin: form.origin,
        },
      });
    },
    onSuccess: () => {
      setForm({ ...EMPTY, target: form.target, system_id: form.system_id });
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) =>
      api<unknown>(ontoPath(tenantId, `/mappings/${id}`), { method: "DELETE" }),
    onSuccess: refresh,
  });

  const targets: { value: string; label: string }[] = [
    {
      value: `concept:${concept.id}`,
      label: `${t("ontomap.mapping.kind.concept")}: ${concept.name}`,
    },
    ...concept.attributes.map((a) => ({
      value: `attribute:${a.id}`,
      label: `${t("ontomap.mapping.kind.attribute")}: ${a.name}`,
    })),
    ...concept.relations
      .filter((r) => r.source_concept_id === concept.id)
      .map((r) => ({
        value: `relation:${r.id}`,
        label: `${t("ontomap.mapping.kind.relation")}: ${r.name}`,
      })),
  ];
  const targetLabel = (kind: MappingKind, id: string) =>
    targets.find((x) => x.value === `${kind}:${id}`)?.label ??
    t(`ontomap.mapping.kind.${kind}`);
  const systemName = (id: string | null) =>
    sources?.systems.find((s) => s.id === id)?.name ?? "";
  const ifLabel = (id: string | null) => {
    const i = sources?.interfaces.find((x) => x.id === id);
    return i ? `${i.if_code} ${i.name}` : "";
  };
  const erdTables = sources?.erd_tables ?? [];
  const columns =
    erdTables.find((x) => x.table === form.table_name)?.columns ?? [];
  const listId = `erd-tables-${concept.id}`;
  const colListId = `erd-columns-${concept.id}`;

  return (
    <section data-testid="mapping-section">
      <h3 className="mb-1 font-semibold">{t("ontomap.mapping.title")}</h3>
      <p className="mb-1 text-xs text-slate-500">{t("ontomap.mapping.hint")}</p>
      <table className="table" data-testid="mapping-table">
        <thead>
          <tr>
            <th>{t("ontomap.mapping.target")}</th>
            <th>{t("ontomap.mapping.system")}</th>
            <th>
              {t("ontomap.mapping.table")}.{t("ontomap.mapping.column")}
            </th>
            <th>{t("ontomap.mapping.interface")}</th>
            <th>{t("ontomap.mapping.origin")}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {concept.mappings.map((m) => (
            <tr key={m.id} data-testid="mapping-row">
              <td>{targetLabel(m.target_kind, m.target_id)}</td>
              <td>{systemName(m.system_id)}</td>
              <td className="font-mono text-xs">
                {[m.table_name, m.column_name].filter(Boolean).join(".")}
              </td>
              <td>{ifLabel(m.interface_id)}</td>
              <td>{t(`ontomap.mapping.originValue.${m.origin}`)}</td>
              <td className="text-right">
                {canWrite && (
                  <button className="btn" onClick={() => remove.mutate(m.id)}>
                    {t("common.delete")}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {canWrite && (
        <form
          className="mt-2 grid grid-cols-2 items-end gap-2 md:grid-cols-4"
          aria-label={t("ontomap.mapping.add")}
          onSubmit={(e) => {
            e.preventDefault();
            add.mutate();
          }}
        >
          <Field label={t("ontomap.mapping.target")}>
            <select
              className="input"
              value={form.target}
              onChange={(e) => setForm({ ...form, target: e.target.value })}
            >
              {targets.map((x) => (
                <option key={x.value} value={x.value}>
                  {x.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("ontomap.mapping.system")}>
            <select
              className="input"
              value={form.system_id}
              onChange={(e) => setForm({ ...form, system_id: e.target.value })}
            >
              <option value="">{t("common.none")}</option>
              {sources?.systems.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("ontomap.mapping.table")}>
            <input
              className="input"
              list={listId}
              value={form.table_name}
              onChange={(e) => {
                const table = e.target.value;
                const fromErd = erdTables.some((x) => x.table === table);
                setForm({
                  ...form,
                  table_name: table,
                  origin:
                    fromErd && form.origin === "manual"
                      ? "exmigrate"
                      : form.origin,
                });
              }}
            />
            <datalist id={listId}>
              {erdTables.map((x) => (
                <option key={`${x.analysis_id}:${x.table}`} value={x.table}>
                  {[x.label, x.filename].filter(Boolean).join(" / ")}
                </option>
              ))}
            </datalist>
          </Field>
          <Field label={t("ontomap.mapping.column")}>
            <input
              className="input"
              list={colListId}
              value={form.column_name}
              onChange={(e) =>
                setForm({ ...form, column_name: e.target.value })
              }
            />
            <datalist id={colListId}>
              {columns.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </Field>
          <Field label={t("ontomap.mapping.interface")}>
            <select
              className="input"
              value={form.interface_id}
              onChange={(e) => {
                const id = e.target.value;
                setForm({
                  ...form,
                  interface_id: id,
                  origin:
                    id && form.origin === "manual" ? "interface" : form.origin,
                });
              }}
            >
              <option value="">{t("common.none")}</option>
              {sources?.interfaces.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.if_code} {i.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("ontomap.mapping.origin")}>
            <Select
              value={form.origin}
              onChange={(v) => setForm({ ...form, origin: v })}
              options={MAPPING_ORIGINS}
              group="ontomap.mapping.originValue"
            />
          </Field>
          <button className="btn">{t("ontomap.mapping.add")}</button>
          <div className="col-span-full">
            {erdTables.length > 0 && (
              <p className="text-xs text-slate-500">
                {t("ontomap.mapping.erdHint")}
              </p>
            )}
            <ErrorText error={add.error} />
          </div>
        </form>
      )}
    </section>
  );
}
