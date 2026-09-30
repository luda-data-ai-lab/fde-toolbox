import type { Task, TaskStatus } from "../../api/types";

export const TASK_STATUSES: TaskStatus[] = ["todo", "in_progress", "review", "done", "on_hold"];
export const PRIORITIES = ["low", "medium", "high", "urgent"] as const;
const PRIORITY_RANK: Record<string, number> = { urgent: 0, high: 1, medium: 2, low: 3 };

export function groupByStatus(tasks: Task[]): Record<TaskStatus, Task[]> {
  const out = Object.fromEntries(TASK_STATUSES.map((s) => [s, [] as Task[]])) as Record<TaskStatus, Task[]>;
  for (const task of tasks) (out[task.status] ?? out.todo).push(task);
  for (const list of Object.values(out))
    list.sort((a, b) => (PRIORITY_RANK[a.priority] ?? 9) - (PRIORITY_RANK[b.priority] ?? 9) || a.title.localeCompare(b.title));
  return out;
}
