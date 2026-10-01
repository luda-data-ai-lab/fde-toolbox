import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type { OntoTerm, Page } from "../../api/types";
import {
  Empty,
  ErrorText,
  Field,
  Select,
  StatusBadge,
} from "../../components/ui";
import { useCanWrite } from "../../app/hooks";
import {
  TERM_STATUSES,
  formatAliases,
  ontoKeys,
  ontoPath,
  parseAliases,
} from "./shared";

const EMPTY = {
  term: "",
  definition: "",
  abbreviation: "",
  aliases: "",
  status: "confirmed",
  notes: "",
};
type FormState = typeof EMPTY;

function toForm(x: OntoTerm): FormState {
  return {
    term: x.term,
    definition: x.definition ?? "",
    abbreviation: x.abbreviation ?? "",
    aliases: formatAliases(x.aliases),
    status: x.status,
    notes: x.notes ?? "",
  };
}

function TermForm({
  tenantId,
  editing,
  onDone,
}: {
  tenantId: string;
  editing: OntoTerm | null;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const [form, setForm] = useState<FormState>(
    editing ? toForm(editing) : EMPTY,
  );
  const save = useMutation({
    mutationFn: () => {
      const body = {
        term: form.term,
        definition: form.definition || null,
        abbreviation: form.abbreviation || null,
        notes: form.notes || null,
        status: form.status,
        aliases: parseAliases(form.aliases),
      };
      return editing
        ? api<OntoTerm>(ontoPath(tenantId, `/terms/${editing.id}`), {
            method: "PATCH",
            body,
          })
        : api<OntoTerm>(ontoPath(tenantId, "/terms"), { method: "POST", body });
    },
    onSuccess: () => {
      setForm(EMPTY);
      onDone();
    },
  });
  const set = (k: keyof FormState) => (v: string) =>
    setForm((f) => ({ ...f, [k]: v }));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };
  return (
    <form
      onSubmit={submit}
      className="card grid grid-cols-2 items-end gap-3 md:grid-cols-4"
      aria-label={editing ? t("ontomap.term.edit") : t("ontomap.term.new")}
    >
      <Field label={t("ontomap.field.term")}>
        <input
          className="input"
          required
          value={form.term}
          onChange={(e) => set("term")(e.target.value)}
        />
      </Field>
      <Field label={t("ontomap.field.abbreviation")}>
        <input
          className="input"
          value={form.abbreviation}
          onChange={(e) => set("abbreviation")(e.target.value)}
        />
      </Field>
      <Field label={t("common.status")}>
        <Select
          value={form.status}
          onChange={set("status")}
          options={TERM_STATUSES}
          group="termStatus"
        />
      </Field>
      <Field label={t("ontomap.field.aliases")}>
        <input
          className="input"
          placeholder={t("ontomap.aliasHint")}
          value={form.aliases}
          onChange={(e) => set("aliases")(e.target.value)}
        />
      </Field>
      <div className="col-span-2">
        <Field label={t("ontomap.field.definition")}>
          <input
            className="input"
            value={form.definition}
            onChange={(e) => set("definition")(e.target.value)}
          />
        </Field>
      </div>
      <Field label={t("common.notes")}>
        <input
          className="input"
          value={form.notes}
          onChange={(e) => set("notes")(e.target.value)}
        />
      </Field>
      <div className="flex gap-2">
        <button className="btn btn-primary">
          {editing ? t("common.save") : t("common.create")}
        </button>
        {editing && (
          <button type="button" className="btn" onClick={onDone}>
            {t("common.cancel")}
          </button>
        )}
      </div>
      <div className="col-span-full">
        <ErrorText error={save.error} />
      </div>
    </form>
  );
}

export function GlossaryView({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const keys = ontoKeys(tenantId);
  const [filters, setFilters] = useState({ q: "", status: "", department: "" });
  const [editing, setEditing] = useState<OntoTerm | null>(null);
  const { data } = useQuery({
    queryKey: keys.terms(filters),
    queryFn: () =>
      api<Page<OntoTerm>>(ontoPath(tenantId, "/terms"), {
        query: { ...filters, limit: 200 },
      }),
  });
  const refresh = () => void qc.invalidateQueries({ queryKey: keys.all });
  const remove = useMutation({
    mutationFn: (id: string) =>
      api<unknown>(ontoPath(tenantId, `/terms/${id}`), { method: "DELETE" }),
    onSuccess: refresh,
  });
  const setFilter = (k: keyof typeof filters) => (v: string) =>
    setFilters((f) => ({ ...f, [k]: v }));
  return (
    <div className="space-y-4">
      {canWrite && (
        <TermForm
          key={editing?.id ?? "new"}
          tenantId={tenantId}
          editing={editing}
          onDone={() => {
            setEditing(null);
            refresh();
          }}
        />
      )}
      <div className="card grid grid-cols-3 gap-3">
        <Field label={t("common.search")}>
          <input
            className="input"
            value={filters.q}
            onChange={(e) => setFilter("q")(e.target.value)}
          />
        </Field>
        <Field label={t("common.status")}>
          <Select
            value={filters.status}
            onChange={setFilter("status")}
            options={TERM_STATUSES}
            group="termStatus"
            allowEmpty
          />
        </Field>
        <Field label={t("ontomap.field.department")}>
          <input
            className="input"
            value={filters.department}
            onChange={(e) => setFilter("department")(e.target.value)}
          />
        </Field>
      </div>
      <div className="card">
        {!data?.items.length ? (
          <Empty />
        ) : (
          <table className="table" data-testid="term-table">
            <thead>
              <tr>
                <th>{t("ontomap.field.term")}</th>
                <th>{t("ontomap.field.definition")}</th>
                <th>{t("ontomap.field.aliases")}</th>
                <th>{t("ontomap.field.abbreviation")}</th>
                <th>{t("common.status")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((x) => (
                <tr key={x.id} data-testid="term-row">
                  <td className="font-medium">{x.term}</td>
                  <td>
                    {x.definition ??
                      (x.status === "confirmed" && (
                        <span className="text-xs text-amber-700">
                          {t("ontomap.noDefinition")}
                        </span>
                      ))}
                  </td>
                  <td className="space-x-1">
                    {x.aliases.map((a) => (
                      <span
                        key={`${a.department ?? ""}:${a.alias}`}
                        className="badge"
                      >
                        {a.department ? `${a.department}: ${a.alias}` : a.alias}
                      </span>
                    ))}
                  </td>
                  <td>{x.abbreviation}</td>
                  <td>
                    <StatusBadge group="termStatus" value={x.status} />
                  </td>
                  <td className="space-x-1 text-right whitespace-nowrap">
                    {canWrite && (
                      <>
                        <button className="btn" onClick={() => setEditing(x)}>
                          {t("common.edit")}
                        </button>
                        <button
                          className="btn btn-danger"
                          onClick={() => remove.mutate(x.id)}
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
