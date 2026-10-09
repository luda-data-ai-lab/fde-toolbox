import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, tenantPath } from "../../api/client";
import type { Issue, Page, Project, ProjectDashboard, Prompt, SpecDocumentSummary, Task } from "../../api/types";
import { Empty, ErrorText, Field, Loading, NeedTenant, PageHeader, Select, StatusBadge } from "../../components/ui";
import { useCanWrite, useTenantId } from "../../app/hooks";
import { PRIORITIES, TASK_STATUSES, groupByStatus } from "./kanban";
import { fmtDate } from "../../app/format";

const PROJECT_STATUSES = ["planning", "active", "on_hold", "done"] as const;
const ISSUE_KINDS = ["bug", "improvement", "question"] as const;
const ISSUE_STATUSES = ["open", "in_progress", "resolved", "closed"] as const;

function LinkedSpecs({ tenantId, project }: { tenantId: string; project: Project }) {
  const { t } = useTranslation();
  const docs = useQuery({
    queryKey: ["specforge", tenantId, "linked", project.engagement_id],
    queryFn: () =>
      api<Page<SpecDocumentSummary>>(tenantPath(tenantId, "/specforge/documents"), {
        query: { limit: 200, engagement_id: project.engagement_id },
      }),
    enabled: project.spec_document_ids.length > 0,
  });
  if (!project.spec_document_ids.length) return null;
  const byId = new Map((docs.data?.items ?? []).map((d) => [d.id, d]));
  return (
    <section className="card" data-testid="linked-specs">
      <h2 className="mb-2 font-semibold">{t("devtracker.specDocs")}</h2>
      <ul className="flex flex-wrap gap-3 text-sm">
        {project.spec_document_ids.map((id) => {
          const d = byId.get(id);
          return (
            <li key={id}>
              <Link className="text-blue-700 hover:underline" to={`/specforge?doc=${id}`}>
                {d ? `${d.title} (${t(`specDocType.${d.doc_type}`)})` : id}
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Issues({ tenantId, projectId }: { tenantId: string; projectId: string }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const sourceId = params.get("issue_from");
  const [adding, setAdding] = useState(!!sourceId);
  const [form, setForm] = useState({
    title: params.get("title") ?? "",
    kind: "bug",
    priority: "medium",
    description: "",
  });
  const key = ["issues", tenantId, projectId];
  const base = tenantPath(tenantId, "/devtracker");
  const issues = useQuery({
    queryKey: key,
    queryFn: () => api<Page<Issue>>(`${base}/projects/${projectId}/issues`, { query: { limit: 200 } }),
  });
  const done = () => void qc.invalidateQueries({ queryKey: key });
  const create = useMutation({
    mutationFn: () =>
      api<Issue>(`${base}/projects/${projectId}/issues`, {
        method: "POST",
        body: {
          ...form,
          description: form.description || null,
          source: sourceId ? { module: "agenthub", instance_id: sourceId } : null,
        },
      }),
    onSuccess: () => {
      setForm({ title: "", kind: "bug", priority: "medium", description: "" });
      setAdding(false);
      if (sourceId) setParams({});
      done();
    },
  });
  const patch = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api<Issue>(`${base}/issues/${id}`, { method: "PATCH", body: { status } }),
    onSuccess: done,
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  const list = issues.data?.items ?? [];
  return (
    <section className="card space-y-3" data-testid="issues">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">{t("devtracker.issues")}</h2>
        {canWrite && !adding && (
          <button type="button" className="btn" onClick={() => setAdding(true)}>
            {t("devtracker.addIssue")}
          </button>
        )}
      </div>
      {canWrite && adding && (
        <form onSubmit={submit} className="grid grid-cols-5 items-end gap-3" data-testid="issue-form">
          {sourceId && (
            <p className="col-span-5 text-sm text-blue-700" data-testid="issue-from-agent">
              {t("devtracker.fromAgent")}
            </p>
          )}
          <Field label={t("common.title")}>
            <input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
          </Field>
          <Field label={t("devtracker.issueKind")}>
            <Select value={form.kind} options={ISSUE_KINDS} group="issueKind" onChange={(kind) => setForm({ ...form, kind })} />
          </Field>
          <Field label={t("devtracker.priority")}>
            <Select value={form.priority} options={PRIORITIES} group="priority" onChange={(priority) => setForm({ ...form, priority })} />
          </Field>
          <Field label={t("common.description")}>
            <input className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
          <button className="btn btn-primary w-fit">{t("common.save")}</button>
          <ErrorText error={create.error} />
        </form>
      )}
      <ErrorText error={patch.error} />
      {!list.length ? (
        <Empty />
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>{t("common.title")}</th>
              <th>{t("devtracker.issueKind")}</th>
              <th>{t("devtracker.priority")}</th>
              <th>{t("common.status")}</th>
              <th>{t("devtracker.issueSource")}</th>
            </tr>
          </thead>
          <tbody>
            {list.map((x) => (
              <tr key={x.id}>
                <td>
                  {x.title}
                  {x.description && <div className="text-xs text-slate-500">{x.description}</div>}
                </td>
                <td>{t(`issueKind.${x.kind}`)}</td>
                <td>{t(`priority.${x.priority}`)}</td>
                <td className="w-40">
                  {canWrite ? (
                    <Select
                      value={x.status}
                      options={ISSUE_STATUSES}
                      group="issueStatus"
                      onChange={(status) => patch.mutate({ id: x.id, status })}
                      ariaLabel={t("common.status")}
                    />
                  ) : (
                    t(`issueStatus.${x.status}`)
                  )}
                </td>
                <td>{x.source ? "AgentHub" : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Dashboard({ d }: { d: ProjectDashboard }) {
  const { t } = useTranslation();
  return (
    <section className="grid grid-cols-4 gap-3" data-testid="project-dashboard">
      <div className="card">
        <div className="label">{t("devtracker.progress")}</div>
        <div className="text-2xl font-semibold">{Math.round(d.progress * 100)}%</div>
        <div className="mt-2 h-2 rounded bg-slate-100">
          <div className="h-2 rounded bg-blue-600" style={{ width: `${Math.round(d.progress * 100)}%` }} />
        </div>
      </div>
      <div className="card">
        <div className="label">{t("devtracker.totalTasks")}</div>
        <div className="text-2xl font-semibold">{d.total_tasks}</div>
        <div className="mt-1 flex flex-wrap gap-1">
          {Object.entries(d.status_counts).map(([s, n]) => (
            <span key={s} className="badge">
              {t(`taskStatus.${s}`)} {n}
            </span>
          ))}
        </div>
      </div>
      <div className="card">
        <div className="label">{t("devtracker.overdue")}</div>
        <ul className="text-sm">{d.overdue_tasks.map((x) => <li key={x.id}>{x.title}</li>)}</ul>
      </div>
      <div className="card">
        <div className="label">{t("devtracker.recentPrompts")}</div>
        <ul className="text-sm">
          {d.recent_prompts.map((p) => (
            <li key={p.id} className="truncate">
              <span className="badge">{p.tool}</span> {p.prompt}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function TaskCard({ task, onOpen }: { task: Task; onOpen: () => void }) {
  const { t } = useTranslation();
  return (
    <button onClick={onOpen} className="w-full rounded border border-slate-200 bg-white p-2 text-left text-sm shadow-sm hover:border-blue-400">
      <div className="font-medium">{task.title}</div>
      <div className="mt-1 flex gap-1">
        <StatusBadge group="priority" value={task.priority} />
        {task.due && <span className="badge">{task.due}</span>}
      </div>
      {task.pause_note && <div className="mt-1 text-xs text-amber-700">⏸ {task.pause_note}</div>}
      <span className="sr-only">{t(`taskStatus.${task.status}`)}</span>
    </button>
  );
}

function TaskPanel({ tenantId, task, onChanged }: { tenantId: string; task: Task; onChanged: () => void }) {
  const { t } = useTranslation();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const [pause, setPause] = useState({ pause_note: task.pause_note ?? "", resume_note: task.resume_note ?? "" });
  const [prompt, setPrompt] = useState({ tool: "devin", prompt: "", result_summary: "" });
  const base = tenantPath(tenantId, `/devtracker/tasks/${task.id}`);
  const prompts = useQuery({
    queryKey: ["prompts", tenantId, task.id],
    queryFn: () => api<Page<Prompt>>(`${base}/prompts`, { query: { limit: 100 } }),
  });
  const patch = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Task>(base, { method: "PATCH", body }),
    onSuccess: onChanged,
  });
  const doPause = useMutation({
    mutationFn: () => api<Task>(`${base}/pause`, { method: "POST", body: pause }),
    onSuccess: onChanged,
  });
  const doResume = useMutation({
    mutationFn: () => api<Task>(`${base}/resume`, { method: "POST" }),
    onSuccess: onChanged,
  });
  const addPrompt = useMutation({
    mutationFn: () => api<Prompt>(`${base}/prompts`, { method: "POST", body: prompt }),
    onSuccess: () => {
      setPrompt({ ...prompt, prompt: "", result_summary: "" });
      void qc.invalidateQueries({ queryKey: ["prompts", tenantId, task.id] });
      onChanged();
    },
  });
  const submitPrompt = (e: FormEvent) => {
    e.preventDefault();
    addPrompt.mutate();
  };
  return (
    <aside className="card w-96 shrink-0 space-y-3" data-testid="task-panel">
      <h2 className="font-semibold">{task.title}</h2>
      {task.description && <p className="text-sm text-slate-600">{task.description}</p>}
      {canWrite && (
        <div className="grid grid-cols-2 gap-2">
          <Field label={t("common.status")}>
            <Select value={task.status} options={TASK_STATUSES} group="taskStatus" onChange={(status) => patch.mutate({ status })} />
          </Field>
          <Field label={t("devtracker.priority")}>
            <Select value={task.priority} options={PRIORITIES} group="priority" onChange={(priority) => patch.mutate({ priority })} />
          </Field>
        </div>
      )}
      <div className="space-y-2 rounded border border-amber-200 bg-amber-50 p-2">
        <Field label={t("devtracker.pauseNote")}>
          <textarea className="input" value={pause.pause_note} onChange={(e) => setPause({ ...pause, pause_note: e.target.value })} disabled={!canWrite} />
        </Field>
        <Field label={t("devtracker.resumeNote")}>
          <textarea className="input" value={pause.resume_note} onChange={(e) => setPause({ ...pause, resume_note: e.target.value })} disabled={!canWrite} />
        </Field>
        {canWrite && (
          <div className="flex gap-2">
            <button className="btn" onClick={() => doPause.mutate()} disabled={!pause.pause_note}>
              {t("devtracker.pause")}
            </button>
            <button className="btn" onClick={() => doResume.mutate()} disabled={task.status !== "on_hold"}>
              {t("devtracker.resume")}
            </button>
          </div>
        )}
      </div>
      <ErrorText error={patch.error ?? doPause.error ?? doResume.error} />
      <div>
        <h3 className="label">{t("devtracker.prompts")}</h3>
        <ul className="max-h-64 space-y-2 overflow-auto text-sm">
          {prompts.data?.items.map((p) => (
            <li key={p.id} className="rounded bg-slate-50 p-2">
              <div className="text-xs text-slate-500">
                {p.tool} · {fmtDate(p.at)}
              </div>
              <div className="whitespace-pre-wrap">{p.prompt}</div>
              {p.result_summary && <div className="mt-1 text-xs text-slate-600">→ {p.result_summary}</div>}
            </li>
          ))}
        </ul>
        {canWrite && (
          <form onSubmit={submitPrompt} className="mt-2 space-y-2">
            <input className="input" value={prompt.tool} onChange={(e) => setPrompt({ ...prompt, tool: e.target.value })} aria-label={t("devtracker.tool")} required />
            <textarea className="input" placeholder={t("devtracker.prompt")} value={prompt.prompt} onChange={(e) => setPrompt({ ...prompt, prompt: e.target.value })} required />
            <input className="input" placeholder={t("devtracker.resultSummary")} value={prompt.result_summary} onChange={(e) => setPrompt({ ...prompt, result_summary: e.target.value })} />
            <button className="btn btn-primary">{t("devtracker.addPrompt")}</button>
            <ErrorText error={addPrompt.error} />
          </form>
        )}
      </div>
    </aside>
  );
}

export function ProjectPage() {
  const { t } = useTranslation();
  const { projectId } = useParams();
  const tenantId = useTenantId();
  const canWrite = useCanWrite();
  const qc = useQueryClient();
  const [view, setView] = useState<"kanban" | "list">("kanban");
  const [openId, setOpenId] = useState<string | null>(null);
  const [newTask, setNewTask] = useState({ title: "", priority: "medium", due: "" });
  const base = tenantPath(tenantId ?? "", `/devtracker/projects/${projectId}`);
  const project = useQuery({ queryKey: ["project", tenantId, projectId], queryFn: () => api<Project>(base), enabled: !!tenantId });
  const dashboard = useQuery({
    queryKey: ["dashboard", tenantId, projectId],
    queryFn: () => api<ProjectDashboard>(`${base}/dashboard`),
    enabled: !!tenantId,
  });
  const tasks = useQuery({
    queryKey: ["tasks", tenantId, projectId],
    queryFn: () => api<Page<Task>>(`${base}/tasks`, { query: { limit: 200 } }),
    enabled: !!tenantId,
  });
  const refresh = () => {
    for (const k of ["tasks", "dashboard", "project"]) void qc.invalidateQueries({ queryKey: [k, tenantId, projectId] });
  };
  const create = useMutation({
    mutationFn: () =>
      api<Task>(`${base}/tasks`, { method: "POST", body: { ...newTask, due: newTask.due || null } }),
    onSuccess: () => {
      setNewTask({ title: "", priority: "medium", due: "" });
      refresh();
    },
  });
  const setStatus = useMutation({
    mutationFn: (body: { status: string }) => api<Project>(base, { method: "PATCH", body }),
    onSuccess: refresh,
  });
  if (!tenantId) return <NeedTenant />;
  if (project.error) return <ErrorText error={project.error} />;
  if (!project.data) return <Loading />;
  const list = tasks.data?.items ?? [];
  const open = list.find((x) => x.id === openId);
  const groups = groupByStatus(list);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  return (
    <div className="space-y-4">
      <PageHeader
        title={project.data.name}
        actions={
          <>
            {canWrite && (
              <div className="w-36">
                <Select value={project.data.status} options={PROJECT_STATUSES} group="projectStatus" onChange={(status) => setStatus.mutate({ status })} ariaLabel={t("common.status")} />
              </div>
            )}
            <button className={`btn ${view === "kanban" ? "btn-primary" : ""}`} onClick={() => setView("kanban")}>
              {t("devtracker.kanban")}
            </button>
            <button className={`btn ${view === "list" ? "btn-primary" : ""}`} onClick={() => setView("list")}>
              {t("devtracker.list")}
            </button>
          </>
        }
      />
      {dashboard.data && <Dashboard d={dashboard.data} />}
      <LinkedSpecs tenantId={tenantId} project={project.data} />
      {canWrite && (
        <form onSubmit={submit} className="card grid grid-cols-4 items-end gap-3">
          <Field label={t("common.title")}>
            <input className="input" value={newTask.title} onChange={(e) => setNewTask({ ...newTask, title: e.target.value })} required />
          </Field>
          <Field label={t("devtracker.priority")}>
            <Select value={newTask.priority} options={PRIORITIES} group="priority" onChange={(priority) => setNewTask({ ...newTask, priority })} />
          </Field>
          <Field label={t("devtracker.due")}>
            <input className="input" type="date" value={newTask.due} onChange={(e) => setNewTask({ ...newTask, due: e.target.value })} />
          </Field>
          <button className="btn btn-primary w-fit">{t("devtracker.addTask")}</button>
          <ErrorText error={create.error} />
        </form>
      )}
      <div className="flex gap-4">
        <div className="min-w-0 flex-1">
          {!list.length ? (
            <div className="card">
              <Empty />
            </div>
          ) : view === "kanban" ? (
            <div className="grid grid-cols-5 gap-3" data-testid="kanban">
              {TASK_STATUSES.map((s) => (
                <div key={s} className="rounded-lg bg-slate-100 p-2">
                  <h3 className="mb-2 text-xs font-semibold text-slate-600">
                    {t(`taskStatus.${s}`)} ({groups[s].length})
                  </h3>
                  <div className="space-y-2">
                    {groups[s].map((task) => (
                      <TaskCard key={task.id} task={task} onOpen={() => setOpenId(task.id)} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="card">
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("common.title")}</th>
                    <th>{t("common.status")}</th>
                    <th>{t("devtracker.priority")}</th>
                    <th>{t("devtracker.due")}</th>
                    <th>{t("devtracker.pauseNote")}</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((task) => (
                    <tr key={task.id} className="cursor-pointer hover:bg-slate-50" onClick={() => setOpenId(task.id)}>
                      <td>{task.title}</td>
                      <td>
                        <StatusBadge group="taskStatus" value={task.status} />
                      </td>
                      <td>{t(`priority.${task.priority}`)}</td>
                      <td>{task.due}</td>
                      <td className="text-amber-700">{task.pause_note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        {open && <TaskPanel key={open.id} tenantId={tenantId} task={open} onChanged={refresh} />}
      </div>
      <Issues tenantId={tenantId} projectId={project.data.id} />
    </div>
  );
}
