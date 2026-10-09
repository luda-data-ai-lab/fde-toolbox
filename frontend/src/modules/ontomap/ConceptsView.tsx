import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import type {
  OntoConcept,
  OntoConceptDetail,
  Page,
  UpperOntology,
  UpperRef,
} from "../../api/types";
import {
  Empty,
  ErrorText,
  Field,
  Select,
  StatusBadge,
} from "../../components/ui";
import { useCanWrite } from "../../app/hooks";
import {
  CARDINALITIES,
  CONCEPT_STATUSES,
  DATA_TYPES,
  ontoKeys,
  ontoPath,
} from "./shared";

type ParentBody = {
  parent_ref: UpperRef | null;
  parent_concept_id: string | null;
};

/** Select value: "" | "c:<concept id>" | "u:<asset id>:<version>:<concept key>" */
function parentValue(
  c: Pick<OntoConcept, "parent_ref" | "parent_concept_id">,
): string {
  if (c.parent_concept_id) return `c:${c.parent_concept_id}`;
  if (c.parent_ref)
    return `u:${c.parent_ref.asset_id}:${c.parent_ref.version}:${c.parent_ref.concept_key}`;
  return "";
}

function parentBody(v: string): ParentBody {
  if (v.startsWith("c:"))
    return { parent_ref: null, parent_concept_id: v.slice(2) };
  if (v.startsWith("u:")) {
    const [assetId = "", version, ...key] = v.slice(2).split(":");
    return {
      parent_ref: {
        asset_id: assetId,
        version: Number(version),
        concept_key: key.join(":"),
      },
      parent_concept_id: null,
    };
  }
  return { parent_ref: null, parent_concept_id: null };
}

function useConceptData(tenantId: string) {
  const keys = ontoKeys(tenantId);
  const concepts = useQuery({
    queryKey: keys.concepts,
    queryFn: () =>
      api<Page<OntoConcept>>(ontoPath(tenantId, "/concepts"), {
        query: { limit: 200 },
      }),
  });
  const upper = useQuery({
    queryKey: keys.upper,
    queryFn: () =>
      api<UpperOntology[]>(ontoPath(tenantId, "/upper-ontologies")),
  });
  return { concepts: concepts.data?.items ?? [], upper: upper.data ?? [] };
}

function ParentSelect({
  value,
  onChange,
  concepts,
  upper,
  excludeId,
  ariaLabel,
}: {
  value: string;
  onChange: (v: string) => void;
  concepts: OntoConcept[];
  upper: UpperOntology[];
  excludeId?: string;
  ariaLabel?: string;
}) {
  const { t } = useTranslation();
  return (
    <select
      className="input"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label={ariaLabel}
    >
      <option value="">{t("common.none")}</option>
      {upper.map((u) => (
        <optgroup
          key={u.asset_id}
          label={`${t("assetType.upper_ontology")}: ${u.title} v${u.version}`}
        >
          {u.concepts.map((c) => (
            <option key={c.key} value={`u:${u.asset_id}:${u.version}:${c.key}`}>
              {c.name} ({c.key})
            </option>
          ))}
        </optgroup>
      ))}
      <optgroup label={t("ontomap.concept.tenantConcepts")}>
        {concepts
          .filter((c) => c.id !== excludeId)
          .map((c) => (
            <option key={c.id} value={`c:${c.id}`}>
              {c.name}
            </option>
          ))}
      </optgroup>
    </select>
  );
}

const EMPTY = {
  name: "",
  definition: "",
  owner_dept: "",
  status: "draft",
  parent: "",
};

function ConceptForm({
  tenantId,
  onCreated,
}: {
  tenantId: string;
  onCreated: (id: string) => void;
}) {
  const { t } = useTranslation();
  const { concepts, upper } = useConceptData(tenantId);
  const [form, setForm] = useState(EMPTY);
  const save = useMutation({
    mutationFn: () =>
      api<OntoConceptDetail>(ontoPath(tenantId, "/concepts"), {
        method: "POST",
        body: {
          name: form.name,
          definition: form.definition || null,
          owner_dept: form.owner_dept || null,
          status: form.status,
          ...parentBody(form.parent),
        },
      }),
    onSuccess: (c) => {
      setForm(EMPTY);
      onCreated(c.id);
    },
  });
  const set = (k: keyof typeof EMPTY) => (v: string) =>
    setForm((f) => ({ ...f, [k]: v }));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };
  return (
    <form
      onSubmit={submit}
      className="card grid grid-cols-2 items-end gap-3 md:grid-cols-3"
      aria-label={t("ontomap.concept.new")}
    >
      <Field label={t("ontomap.concept.name")}>
        <input
          className="input"
          required
          value={form.name}
          onChange={(e) => set("name")(e.target.value)}
        />
      </Field>
      <Field label={t("ontomap.concept.parent")}>
        <ParentSelect
          value={form.parent}
          onChange={set("parent")}
          concepts={concepts}
          upper={upper}
        />
      </Field>
      <Field label={t("common.status")}>
        <Select
          value={form.status}
          onChange={set("status")}
          options={CONCEPT_STATUSES}
          group="conceptStatus"
        />
      </Field>
      <Field label={t("ontomap.field.definition")}>
        <input
          className="input"
          value={form.definition}
          onChange={(e) => set("definition")(e.target.value)}
        />
      </Field>
      <Field label={t("ontomap.concept.ownerDept")}>
        <input
          className="input"
          value={form.owner_dept}
          onChange={(e) => set("owner_dept")(e.target.value)}
        />
      </Field>
      <button className="btn btn-primary">{t("ontomap.concept.new")}</button>
      <div className="col-span-full">
        <ErrorText error={save.error} />
      </div>
    </form>
  );
}

const EMPTY_ATTR = { name: "", data_type: "string", unit: "", required: false };
const EMPTY_REL = {
  name: "",
  target: "",
  cardinality: "1:N",
  inverse_name: "",
};

function ConceptDetailPanel({
  tenantId,
  conceptId,
  onDeleted,
}: {
  tenantId: string;
  conceptId: string;
  onDeleted: () => void;
}) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const keys = ontoKeys(tenantId);
  const { concepts, upper } = useConceptData(tenantId);
  const { data: c } = useQuery({
    queryKey: keys.concept(conceptId),
    queryFn: () =>
      api<OntoConceptDetail>(ontoPath(tenantId, `/concepts/${conceptId}`)),
  });
  const [attr, setAttr] = useState(EMPTY_ATTR);
  const [rel, setRel] = useState(EMPTY_REL);
  const refresh = () => void qc.invalidateQueries({ queryKey: keys.all });
  const call = (path: string, method: string, body?: Record<string, unknown>) =>
    api<unknown>(ontoPath(tenantId, path), { method, body });
  const patch = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      call(`/concepts/${conceptId}`, "PATCH", body),
    onSuccess: refresh,
  });
  const addAttr = useMutation({
    mutationFn: () =>
      call(`/concepts/${conceptId}/attributes`, "POST", {
        ...attr,
        unit: attr.unit || null,
      }),
    onSuccess: () => {
      setAttr(EMPTY_ATTR);
      refresh();
    },
  });
  const addRel = useMutation({
    mutationFn: () =>
      call("/relations", "POST", {
        source_concept_id: conceptId,
        name: rel.name,
        target_concept_id: rel.target,
        cardinality: rel.cardinality,
        inverse_name: rel.inverse_name || null,
      }),
    onSuccess: () => {
      setRel(EMPTY_REL);
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (path: string) => call(path, "DELETE"),
    onSuccess: refresh,
  });
  const removeConcept = useMutation({
    mutationFn: () => call(`/concepts/${conceptId}`, "DELETE"),
    onSuccess: () => {
      onDeleted();
      refresh();
    },
  });
  if (!c) return null;
  const nameOf = (id: string) => concepts.find((x) => x.id === id)?.name ?? id;
  return (
    <div className="card space-y-4" data-testid="concept-detail">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">{c.name}</h2>
          {c.definition && (
            <p className="text-sm text-slate-600">{c.definition}</p>
          )}
          <p className="text-xs text-slate-500" data-testid="concept-ancestors">
            {[
              c.name,
              ...c.ancestors.map((a) =>
                a.kind === "upper" ? `${a.name} (${a.ontology})` : a.name,
              ),
            ].join(" → ")}
          </p>
        </div>
        <StatusBadge group="conceptStatus" value={c.status} />
      </div>
      {c.warnings.length > 0 && (
        <ul className="text-sm text-amber-700" data-testid="concept-warnings">
          {c.warnings.map((w) => (
            <li key={w.code}>{t(`ontomap.validation.${w.code}`)}</li>
          ))}
        </ul>
      )}
      {canWrite && (
        <div className="grid grid-cols-2 items-end gap-3 md:grid-cols-3">
          <Field label={t("ontomap.concept.changeParent")}>
            <ParentSelect
              value={parentValue(c)}
              onChange={(v) => patch.mutate(parentBody(v))}
              concepts={concepts}
              upper={upper}
              excludeId={c.id}
            />
          </Field>
          <Field label={t("ontomap.concept.changeStatus")}>
            <Select
              value={c.status}
              onChange={(v) => patch.mutate({ status: v })}
              options={CONCEPT_STATUSES}
              group="conceptStatus"
            />
          </Field>
          <button
            type="button"
            className="btn"
            onClick={() => removeConcept.mutate()}
          >
            {t("common.delete")}
          </button>
          <div className="col-span-full">
            <ErrorText error={patch.error ?? removeConcept.error} />
          </div>
        </div>
      )}

      <section>
        <h3 className="mb-1 font-semibold">
          {t("ontomap.concept.attributes")}
        </h3>
        <table className="table" data-testid="attribute-table">
          <thead>
            <tr>
              <th>{t("common.name")}</th>
              <th>{t("ontomap.concept.dataType")}</th>
              <th>{t("ontomap.concept.unit")}</th>
              <th>{t("ontomap.concept.required")}</th>
              <th>{t("ontomap.concept.origin")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {c.attributes.map((a) => (
              <tr key={a.id} data-testid="attribute-row">
                <td className="font-medium">
                  {a.name}
                  {c.id_attribute_id === a.id && (
                    <span className="badge ml-1">
                      {t("ontomap.concept.identifier")}
                    </span>
                  )}
                </td>
                <td>{t(`dataType.${a.data_type}`)}</td>
                <td>{a.unit}</td>
                <td>{a.required ? "✓" : ""}</td>
                <td>{t("ontomap.concept.own")}</td>
                <td className="space-x-1 text-right whitespace-nowrap">
                  {canWrite && c.id_attribute_id !== a.id && (
                    <button
                      className="btn"
                      onClick={() => patch.mutate({ id_attribute_id: a.id })}
                    >
                      {t("ontomap.concept.setIdentifier")}
                    </button>
                  )}
                  {canWrite && (
                    <button
                      className="btn"
                      onClick={() => remove.mutate(`/attributes/${a.id}`)}
                    >
                      {t("common.delete")}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {c.inherited_properties.map((p) => (
              <tr
                key={`${p.origin}:${p.name}`}
                className="text-slate-500"
                data-testid="inherited-row"
              >
                <td>{p.name}</td>
                <td>{p.data_type ? t(`dataType.${p.data_type}`) : ""}</td>
                <td />
                <td />
                <td>
                  {t("ontomap.concept.inheritedFrom", { origin: p.origin })}
                </td>
                <td />
              </tr>
            ))}
          </tbody>
        </table>
        {canWrite && (
          <form
            className="mt-2 grid grid-cols-2 items-end gap-2 md:grid-cols-5"
            aria-label={t("ontomap.concept.addAttribute")}
            onSubmit={(e) => {
              e.preventDefault();
              addAttr.mutate();
            }}
          >
            <Field label={t("ontomap.concept.attributeName")}>
              <input
                className="input"
                required
                value={attr.name}
                onChange={(e) => setAttr({ ...attr, name: e.target.value })}
              />
            </Field>
            <Field label={t("ontomap.concept.dataType")}>
              <Select
                value={attr.data_type}
                onChange={(v) => setAttr({ ...attr, data_type: v })}
                options={DATA_TYPES}
                group="dataType"
              />
            </Field>
            <Field label={t("ontomap.concept.unit")}>
              <input
                className="input"
                value={attr.unit}
                onChange={(e) => setAttr({ ...attr, unit: e.target.value })}
              />
            </Field>
            <label className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={attr.required}
                onChange={(e) =>
                  setAttr({ ...attr, required: e.target.checked })
                }
              />
              {t("ontomap.concept.required")}
            </label>
            <button className="btn">{t("ontomap.concept.addAttribute")}</button>
            <div className="col-span-full">
              <ErrorText error={addAttr.error} />
            </div>
          </form>
        )}
      </section>

      <section>
        <h3 className="mb-1 font-semibold">{t("ontomap.concept.relations")}</h3>
        <table className="table" data-testid="relation-table">
          <thead>
            <tr>
              <th>{t("ontomap.concept.source")}</th>
              <th>{t("ontomap.concept.relationName")}</th>
              <th>{t("ontomap.concept.target")}</th>
              <th>{t("ontomap.concept.cardinality")}</th>
              <th>{t("ontomap.concept.inverse")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {c.relations.map((r) => (
              <tr key={r.id} data-testid="relation-row">
                <td>{nameOf(r.source_concept_id)}</td>
                <td className="font-medium">{r.name}</td>
                <td>{nameOf(r.target_concept_id)}</td>
                <td>{r.cardinality}</td>
                <td>{r.inverse_name}</td>
                <td className="text-right">
                  {canWrite && (
                    <button
                      className="btn"
                      onClick={() => remove.mutate(`/relations/${r.id}`)}
                    >
                      {t("common.delete")}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {c.inherited_relations.map((r) => (
              <tr
                key={`${r.origin}:${r.name}:${r.target}`}
                className="text-slate-500"
              >
                <td>{c.name}</td>
                <td>{r.name}</td>
                <td>{r.target}</td>
                <td />
                <td />
                <td>
                  {t("ontomap.concept.inheritedFrom", { origin: r.origin })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {canWrite && (
          <form
            className="mt-2 grid grid-cols-2 items-end gap-2 md:grid-cols-5"
            aria-label={t("ontomap.concept.addRelation")}
            onSubmit={(e) => {
              e.preventDefault();
              addRel.mutate();
            }}
          >
            <Field label={t("ontomap.concept.relationName")}>
              <input
                className="input"
                required
                value={rel.name}
                onChange={(e) => setRel({ ...rel, name: e.target.value })}
              />
            </Field>
            <Field label={t("ontomap.concept.target")}>
              <select
                className="input"
                required
                value={rel.target}
                onChange={(e) => setRel({ ...rel, target: e.target.value })}
              >
                <option value="">{t("common.none")}</option>
                {concepts.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("ontomap.concept.cardinality")}>
              <Select
                value={rel.cardinality}
                onChange={(v) => setRel({ ...rel, cardinality: v })}
                options={CARDINALITIES}
                group="cardinality"
              />
            </Field>
            <Field label={t("ontomap.concept.inverse")}>
              <input
                className="input"
                value={rel.inverse_name}
                onChange={(e) =>
                  setRel({ ...rel, inverse_name: e.target.value })
                }
              />
            </Field>
            <button className="btn">{t("ontomap.concept.addRelation")}</button>
            <div className="col-span-full">
              <ErrorText error={addRel.error} />
            </div>
          </form>
        )}
      </section>

      {c.terms.length > 0 && (
        <section>
          <h3 className="mb-1 font-semibold">{t("ontomap.concept.terms")}</h3>
          <div className="space-x-1">
            {c.terms.map((x) => (
              <span key={x.id} className="badge">
                {x.term}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export function ConceptsView({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const { concepts } = useConceptData(tenantId);
  const [selected, setSelected] = useState<string | null>(null);
  const nameOf = (c: OntoConcept) =>
    c.parent_concept_id
      ? (concepts.find((x) => x.id === c.parent_concept_id)?.name ?? "")
      : (c.parent_ref?.concept_key ?? "");
  return (
    <div className="space-y-4">
      {canWrite && (
        <ConceptForm
          tenantId={tenantId}
          onCreated={(id) => {
            setSelected(id);
            void qc.invalidateQueries({ queryKey: ontoKeys(tenantId).all });
          }}
        />
      )}
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <div className="card">
          {!concepts.length ? (
            <Empty />
          ) : (
            <table className="table" data-testid="concept-table">
              <thead>
                <tr>
                  <th>{t("ontomap.concept.name")}</th>
                  <th>{t("ontomap.concept.parent")}</th>
                  <th>{t("common.status")}</th>
                </tr>
              </thead>
              <tbody>
                {concepts.map((c) => (
                  <tr
                    key={c.id}
                    data-testid="concept-row"
                    className={`cursor-pointer ${selected === c.id ? "bg-blue-50" : ""}`}
                    onClick={() => setSelected(c.id)}
                  >
                    <td className="font-medium">{c.name}</td>
                    <td>{nameOf(c)}</td>
                    <td>
                      <StatusBadge group="conceptStatus" value={c.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        {selected && (
          <ConceptDetailPanel
            key={selected}
            tenantId={tenantId}
            conceptId={selected}
            onDeleted={() => setSelected(null)}
          />
        )}
      </div>
    </div>
  );
}
