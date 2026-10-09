import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { api, tenantPath } from "../../api/client";
import type { Page, XlAnalysis, XlAnalysisSummary, XlErd, XlErdDraft, XlSheetReport } from "../../api/types";
import { handoffUrl } from "../../app/handoff";
import { useCanWrite, useTenantId } from "../../app/hooks";
import { useWorkspace } from "../../app/store";
import { Empty, ErrorText, Loading, NeedTenant, PageHeader, Select, StatusBadge } from "../../components/ui";
import { EngagementSelect } from "../discoveryq/EngagementSelect";

const COLUMN_TYPES = ["integer", "decimal", "boolean", "date", "datetime", "text"] as const;
const DIALECTS = ["postgresql", "mssql", "sqlite"] as const;
const TABS = ["structure", "formulas", "erd", "scripts"] as const;
type Tab = (typeof TABS)[number];

const keys = (tenantId: string) => ({
  all: ["exmigrate", tenantId] as const,
  list: (engagementId: string) => ["exmigrate", tenantId, "list", engagementId] as const,
  one: (id: string) => ["exmigrate", tenantId, "analysis", id] as const,
  erd: (id: string) => ["exmigrate", tenantId, "erd", id] as const,
});
const xlPath = (tenantId: string, path: string) => tenantPath(tenantId, `/exmigrate${path}`);

export function ExMigratePage() {
  const { t } = useTranslation();
  const tenantId = useTenantId();
  const [params, setParams] = useSearchParams();
  const id = params.get("analysis");
  if (!tenantId) return <NeedTenant />;
  const open = (next: string | null) => setParams(next ? { analysis: next } : {});
  return (
    <div className="space-y-4">
      <PageHeader title={t("nav.exmigrate")} />
      {id ? (
        <AnalysisDetail tenantId={tenantId} id={id} onBack={() => open(null)} />
      ) : (
        <AnalysisList tenantId={tenantId} onOpen={open} />
      )}
    </div>
  );
}

function AnalysisList({ tenantId, onOpen }: { tenantId: string; onOpen: (id: string) => void }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const workspaceEngagement = useWorkspace((s) => s.engagementId);
  const [engagementId, setEngagementId] = useState("");
  const engagement = engagementId || workspaceEngagement || "";
  const input = useRef<HTMLInputElement>(null);
  const { data, isLoading } = useQuery({
    queryKey: keys(tenantId).list(engagement),
    queryFn: () =>
      api<Page<XlAnalysisSummary>>(xlPath(tenantId, "/analyses"), {
        query: { limit: 200, engagement_id: engagement },
      }),
  });
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("engagement_id", engagement);
      form.append("file", file);
      return api<XlAnalysis>(xlPath(tenantId, "/analyses"), {
        method: "POST",
        body: form,
      });
    },
    onSuccess: (a) => {
      void qc.invalidateQueries({ queryKey: keys(tenantId).all });
      onOpen(a.id);
    },
  });
  const items = data?.items ?? [];
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{t("exmigrate.intro")}</p>
      <div className="card flex flex-wrap items-end gap-3">
        <EngagementSelect tenantId={tenantId} value={engagementId} onChange={setEngagementId} optional />
        {canWrite &&
          (engagement ? (
            <>
              <input ref={input} type="file" accept=".xlsx,.xlsm" aria-label={t("exmigrate.file")} />
              <button
                className="btn-primary"
                disabled={upload.isPending}
                onClick={() => {
                  const file = input.current?.files?.[0];
                  if (file) upload.mutate(file);
                }}
              >
                {t("exmigrate.upload")}
              </button>
            </>
          ) : (
            <p className="text-sm text-slate-500">{t("exmigrate.needEngagement")}</p>
          ))}
        <ErrorText error={upload.error} />
      </div>
      <div className="card">
        {isLoading ? (
          <Loading />
        ) : items.length === 0 ? (
          <Empty />
        ) : (
          <table className="table" data-testid="xl-list">
            <thead>
              <tr>
                <th>{t("exmigrate.field.filename")}</th>
                <th>{t("exmigrate.field.sheets")}</th>
                <th>{t("exmigrate.field.formulas")}</th>
                <th>{t("exmigrate.field.erd")}</th>
                <th>{t("exmigrate.field.created")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id}>
                  <td>
                    <button className="text-left text-brand-700 hover:underline" onClick={() => onOpen(a.id)}>
                      {a.filename}
                    </button>
                  </td>
                  <td>{a.sheets}</td>
                  <td>{a.formula_count}</td>
                  <td>{a.erd_confirmed ? t("exmigrate.erdConfirmed") : t("exmigrate.erdDraft")}</td>
                  <td>{new Date(a.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function AnalysisDetail({ tenantId, id, onBack }: { tenantId: string; id: string; onBack: () => void }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("structure");
  const { data, isLoading, error } = useQuery({
    queryKey: keys(tenantId).one(id),
    queryFn: () => api<XlAnalysis>(xlPath(tenantId, `/analyses/${id}`)),
  });
  const remove = useMutation({
    mutationFn: () => api<unknown>(xlPath(tenantId, `/analyses/${id}`), { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys(tenantId).all });
      onBack();
    },
  });
  if (isLoading) return <Loading />;
  if (!data) return <ErrorText error={error} />;
  const base = `/api/v1${xlPath(tenantId, `/analyses/${id}`)}`;
  const report = data.report;
  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-center gap-2">
        <button className="btn" onClick={onBack}>
          {t("exmigrate.back")}
        </button>
        <h2 className="font-semibold" data-testid="xl-filename">
          {data.filename}
        </h2>
        <span className="text-sm text-slate-500">
          {t("exmigrate.field.sheets")} {data.sheets} · {t("exmigrate.field.formulas")} {data.formula_count}
        </span>
        <div className="ml-auto flex gap-2">
          {canWrite && (
            <>
              <a className="btn" href={`${base}/report.md`}>
                {t("exmigrate.report")}
              </a>
              <a className="btn" href={`${base}/erd.mmd`}>
                {t("exmigrate.mermaid")}
              </a>
              <button
                className="btn"
                onClick={() => {
                  if (window.confirm(t("exmigrate.confirmDelete"))) remove.mutate();
                }}
              >
                {t("exmigrate.delete")}
              </button>
            </>
          )}
        </div>
      </div>
      {report.has_macros && <p className="text-sm text-amber-700">{t("exmigrate.macros")}</p>}
      <div className="flex gap-2" role="tablist">
        {TABS.map((x) => (
          <button
            key={x}
            role="tab"
            aria-selected={tab === x}
            className={tab === x ? "btn-primary" : "btn"}
            onClick={() => setTab(x)}
          >
            {t(`exmigrate.tab.${x}`)}
          </button>
        ))}
      </div>
      {tab === "structure" && report.sheets.map((s) => <SheetStructure key={s.name} sheet={s} />)}
      {tab === "formulas" && <Formulas analysis={data} />}
      {tab === "erd" && <ErdEditor tenantId={tenantId} id={id} engagementId={data.engagement_id} />}
      {tab === "scripts" && <Scripts tenantId={tenantId} id={id} base={base} />}
    </div>
  );
}

function SheetStructure({ sheet }: { sheet: XlSheetReport }) {
  const { t } = useTranslation();
  return (
    <section className="card space-y-2" data-testid="xl-sheet">
      <h3 className="font-semibold">{sheet.name}</h3>
      <p className="text-sm text-slate-600">
        {sheet.dimension} · {t("exmigrate.field.headerRow")} {sheet.header_row ?? "-"} · {t("exmigrate.field.dataRows")}{" "}
        {sheet.data_rows}
      </p>
      {sheet.warnings.length > 0 && (
        <ul className="text-sm text-amber-700" aria-label={t("exmigrate.warnings")}>
          {sheet.warnings.map((w, i) => (
            <li key={i}>
              {t(`exmigrate.warning.${w.code}`, { defaultValue: w.code })}
              {w.where ? ` @ ${w.where}` : ""}
              {w.detail ? `: ${w.detail}` : ""}
            </li>
          ))}
        </ul>
      )}
      {sheet.columns.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>{t("exmigrate.field.column")}</th>
              <th>{t("exmigrate.field.name")}</th>
              <th>{t("exmigrate.field.type")}</th>
              <th>{t("exmigrate.field.nullRatio")}</th>
              <th>{t("exmigrate.field.distinct")}</th>
              <th>{t("exmigrate.field.formulaCells")}</th>
              <th>{t("exmigrate.field.samples")}</th>
            </tr>
          </thead>
          <tbody>
            {sheet.columns.map((c) => (
              <tr key={c.letter}>
                <td>{c.letter}</td>
                <td>{c.name}</td>
                <td>{c.inferred_type ? t(`columnType.${c.inferred_type}`) : "-"}</td>
                <td>{Math.round(c.null_ratio * 1000) / 10}</td>
                <td>{c.distinct}</td>
                <td>{c.formula_cells}</td>
                <td className="text-slate-500">{c.samples.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Formulas({ analysis }: { analysis: XlAnalysis }) {
  const { t } = useTranslation();
  const report = analysis.report;
  if (report.formula_count === 0) return <p className="card text-sm">{t("exmigrate.noFormulas")}</p>;
  return (
    <div className="space-y-4">
      <section className="card space-y-2">
        {report.complex_formulas > 0 && (
          <p className="text-sm text-amber-700">{t("exmigrate.complex", { count: report.complex_formulas })}</p>
        )}
        <table className="table" data-testid="xl-functions">
          <thead>
            <tr>
              <th>{t("exmigrate.field.function")}</th>
              <th>{t("exmigrate.field.count")}</th>
              <th>{t("exmigrate.field.simple")}</th>
            </tr>
          </thead>
          <tbody>
            {report.functions.map((f) => (
              <tr key={f.name}>
                <td>{f.name}</td>
                <td>{f.count}</td>
                <td>{f.simple ? "✓" : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {report.sheets
        .filter((s) => s.formulas.count > 0)
        .map((s) => (
          <section key={s.name} className="card space-y-2">
            <h3 className="font-semibold">
              {s.name} · {s.formulas.count}
            </h3>
            {s.formulas.references.length > 0 && (
              <p className="text-sm">
                {t("exmigrate.references")}: {s.formulas.references.map((r) => `${r.sheet} (${r.count})`).join(", ")}
              </p>
            )}
            {s.formulas.cells.length < s.formulas.count && (
              <p className="text-xs text-slate-500">{t("exmigrate.moreCells", { count: s.formulas.cells.length })}</p>
            )}
            <table className="table">
              <thead>
                <tr>
                  <th>{t("exmigrate.field.cell")}</th>
                  <th>{t("exmigrate.field.formula")}</th>
                </tr>
              </thead>
              <tbody>
                {s.formulas.cells.map((c) => (
                  <tr key={c.cell}>
                    <td>{c.cell}</td>
                    <td className="font-mono text-xs">{c.formula}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ))}
    </div>
  );
}

function ErdEditor({ tenantId, id, engagementId }: { tenantId: string; id: string; engagementId: string }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const path = xlPath(tenantId, `/analyses/${id}/erd`);
  const { data } = useQuery({
    queryKey: keys(tenantId).erd(id),
    queryFn: () => api<XlErdDraft>(path),
  });
  const [edited, setEdited] = useState<XlErd | null>(null);
  const done = (d: XlErdDraft) => {
    qc.setQueryData(keys(tenantId).erd(id), d);
    void qc.invalidateQueries({ queryKey: keys(tenantId).all });
    setEdited(null);
  };
  const save = useMutation({
    mutationFn: (body: XlErd) => api<XlErdDraft>(path, { method: "PUT", body: { ...body } }),
    onSuccess: done,
  });
  const confirm = useMutation({
    mutationFn: () => api<XlErdDraft>(`${path}/confirm`, { method: "POST" }),
    onSuccess: done,
  });
  if (!data) return <Loading />;
  const erd = edited ?? data.erd;
  const dirty = edited !== null;
  const edit = (next: XlErd) => setEdited(next);
  const setTable = (ti: number, patch: Partial<XlErd["tables"][number]>) =>
    edit({
      ...erd,
      tables: erd.tables.map((tb, i) => (i === ti ? { ...tb, ...patch } : tb)),
    });
  const setColumn = (ti: number, ci: number, patch: Partial<XlErd["tables"][number]["columns"][number]>) =>
    setTable(ti, {
      columns: (erd.tables[ti]?.columns ?? []).map((c, i) => (i === ci ? { ...c, ...patch } : c)),
    });
  const tableNames = erd.tables.map((tb) => tb.name);
  const columnsOf = (name: string) => erd.tables.find((tb) => tb.name === name)?.columns.map((c) => c.name) ?? [];
  const setRelation = (ri: number, patch: Partial<XlErd["relations"][number]>) =>
    edit({
      ...erd,
      relations: erd.relations.map((r, i) => (i === ri ? { ...r, ...patch } : r)),
    });
  const readOnly = !canWrite;
  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-center gap-2">
        <span className="badge" data-testid="erd-status">
          {data.confirmed && !dirty ? t("exmigrate.erdConfirmed") : t("exmigrate.erdDraft")}
        </span>
        {canWrite && (
          <>
            <button className="btn" disabled={!dirty || save.isPending} onClick={() => save.mutate(erd)}>
              {dirty ? t("exmigrate.save") : t("exmigrate.saved")}
            </button>
            <button
              className="btn-primary"
              disabled={dirty || data.confirmed || data.issues.length > 0 || confirm.isPending}
              onClick={() => confirm.mutate()}
            >
              {t("exmigrate.confirm")}
            </button>
            {data.confirmed && <span className="text-xs text-slate-500">{t("exmigrate.editAgain")}</span>}
            {data.confirmed && !dirty && engagementId && (
              <Link
                className="btn"
                data-testid="send-specforge"
                to={handoffUrl("/specforge", { engagement: engagementId, analyses: [id] })}
              >
                {t("handoff.toSpecForge")}
              </Link>
            )}
          </>
        )}
        <ErrorText error={save.error ?? confirm.error} />
      </div>
      {data.issues.length > 0 && !dirty && (
        <div className="card text-sm text-red-700" data-testid="erd-issues">
          <p className="font-semibold">{t("exmigrate.issues")}</p>
          <ul>
            {data.issues.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </div>
      )}
      <h3 className="font-semibold">{t("exmigrate.tables")}</h3>
      {erd.tables.map((tb, ti) => (
        <section key={ti} className="card space-y-2" data-testid="erd-table">
          <div className="flex flex-wrap items-center gap-2">
            <input
              className="input max-w-xs"
              aria-label={t("exmigrate.table")}
              value={tb.name}
              disabled={readOnly}
              onChange={(e) => setTable(ti, { name: e.target.value })}
            />
            <span className="text-sm text-slate-500">{tb.source_sheet}</span>
            {canWrite && (
              <button
                className="btn ml-auto"
                onClick={() =>
                  edit({
                    tables: erd.tables.filter((_, i) => i !== ti),
                    relations: erd.relations.filter((r) => r.from_table !== tb.name && r.to_table !== tb.name),
                  })
                }
              >
                {t("exmigrate.removeTable")}
              </button>
            )}
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>{t("exmigrate.field.name")}</th>
                <th>{t("exmigrate.field.label")}</th>
                <th>{t("exmigrate.field.type")}</th>
                <th>{t("exmigrate.field.pk")}</th>
                <th>{t("exmigrate.field.nullable")}</th>
                <th>{t("exmigrate.field.source")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {tb.columns.map((c, ci) => (
                <tr key={ci}>
                  <td>
                    <input
                      className="input"
                      aria-label={`${tb.name}.${t("exmigrate.field.name")}`}
                      value={c.name}
                      disabled={readOnly}
                      onChange={(e) => setColumn(ti, ci, { name: e.target.value })}
                    />
                  </td>
                  <td className="text-slate-500">{c.label}</td>
                  <td>
                    <Select
                      value={c.type}
                      onChange={(v) =>
                        setColumn(ti, ci, {
                          type: v as XlErd["tables"][number]["columns"][number]["type"],
                        })
                      }
                      options={COLUMN_TYPES}
                      group="columnType"
                      ariaLabel={`${tb.name}.${c.name} ${t("exmigrate.field.type")}`}
                    />
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`${tb.name}.${c.name} PK`}
                      checked={c.primary_key}
                      disabled={readOnly}
                      onChange={(e) => setColumn(ti, ci, { primary_key: e.target.checked })}
                    />
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`${tb.name}.${c.name} NULL`}
                      checked={c.nullable}
                      disabled={readOnly}
                      onChange={(e) => setColumn(ti, ci, { nullable: e.target.checked })}
                    />
                  </td>
                  <td>{c.source_column ?? "-"}</td>
                  <td>
                    {canWrite && tb.columns.length > 1 && (
                      <button
                        className="btn"
                        onClick={() =>
                          setTable(ti, {
                            columns: tb.columns.filter((_, i) => i !== ci),
                          })
                        }
                      >
                        {t("exmigrate.removeColumn")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
      <section className="card space-y-2" data-testid="erd-relations">
        <h3 className="font-semibold">{t("exmigrate.relations")}</h3>
        <table className="table">
          <thead>
            <tr>
              <th>{t("exmigrate.fromTable")}</th>
              <th>{t("exmigrate.fromColumn")}</th>
              <th>{t("exmigrate.toTable")}</th>
              <th>{t("exmigrate.toColumn")}</th>
              <th>{t("exmigrate.origin")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {erd.relations.map((r, ri) => (
              <tr key={ri}>
                <td>
                  <Select
                    value={r.from_table}
                    onChange={(v) =>
                      setRelation(ri, {
                        from_table: v,
                        from_column: columnsOf(v)[0] ?? "",
                      })
                    }
                    options={tableNames}
                    group="_"
                    ariaLabel={t("exmigrate.fromTable")}
                  />
                </td>
                <td>
                  <Select
                    value={r.from_column}
                    onChange={(v) => setRelation(ri, { from_column: v })}
                    options={columnsOf(r.from_table)}
                    group="_"
                    ariaLabel={t("exmigrate.fromColumn")}
                  />
                </td>
                <td>
                  <Select
                    value={r.to_table}
                    onChange={(v) =>
                      setRelation(ri, {
                        to_table: v,
                        to_column: columnsOf(v)[0] ?? "",
                      })
                    }
                    options={tableNames}
                    group="_"
                    ariaLabel={t("exmigrate.toTable")}
                  />
                </td>
                <td>
                  <Select
                    value={r.to_column}
                    onChange={(v) => setRelation(ri, { to_column: v })}
                    options={columnsOf(r.to_table)}
                    group="_"
                    ariaLabel={t("exmigrate.toColumn")}
                  />
                </td>
                <td>
                  <StatusBadge group="relationOrigin" value={r.origin} />
                </td>
                <td>
                  {canWrite && (
                    <button
                      className="btn"
                      onClick={() =>
                        edit({
                          ...erd,
                          relations: erd.relations.filter((_, i) => i !== ri),
                        })
                      }
                    >
                      {t("exmigrate.remove")}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {canWrite && erd.tables.length > 1 && (
          <button
            className="btn"
            onClick={() => {
              const [a, b] = erd.tables;
              const ac = a?.columns[0];
              const bc = b?.columns[0];
              if (!a || !b || !ac || !bc) return;
              edit({
                ...erd,
                relations: [
                  ...erd.relations,
                  {
                    from_table: a.name,
                    from_column: ac.name,
                    to_table: b.name,
                    to_column: bc.name,
                    origin: "manual",
                  },
                ],
              });
            }}
          >
            {t("exmigrate.addRelation")}
          </button>
        )}
      </section>
    </div>
  );
}

function Scripts({ tenantId, id, base }: { tenantId: string; id: string; base: string }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const [dialect, setDialect] = useState<string>("postgresql");
  const erd = useQuery({
    queryKey: keys(tenantId).erd(id),
    queryFn: () => api<XlErdDraft>(xlPath(tenantId, `/analyses/${id}/erd`)),
  });
  const confirmed = erd.data?.confirmed ?? false;
  const ddl = useQuery({
    queryKey: [...keys(tenantId).erd(id), "ddl", dialect, erd.data?.confirmed_at],
    queryFn: async () => {
      const blob = await api<Blob>(xlPath(tenantId, `/analyses/${id}/ddl.sql`), { query: { dialect } });
      return blob.text();
    },
    enabled: confirmed,
  });
  if (!confirmed) return <p className="card text-sm">{t("exmigrate.needConfirm")}</p>;
  return (
    <div className="card space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <label className="block">
          <span className="label">{t("exmigrate.dialect")}</span>
          <Select value={dialect} onChange={setDialect} options={DIALECTS} group="dialect" />
        </label>
        {canWrite && (
          <a className="btn-primary" href={`${base}/scripts.zip?dialect=${dialect}`}>
            {t("exmigrate.downloadScripts")}
          </a>
        )}
      </div>
      <p className="label">{t("exmigrate.preview")}</p>
      {ddl.isLoading ? (
        <Loading />
      ) : (
        <pre className="max-h-[32rem] overflow-auto rounded bg-slate-50 p-3 text-xs" data-testid="ddl-preview">
          {ddl.data}
        </pre>
      )}
      <ErrorText error={ddl.error} />
    </div>
  );
}
