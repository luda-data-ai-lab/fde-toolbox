import type { Task } from "../../api/types";
import { groupByStatus } from "./kanban";

const task = (id: string, status: Task["status"], priority: string): Task => ({
  id, status, priority, title: id, tenant_id: "t", project_id: "p", created_at: "", updated_at: "",
  description: null, assignee_id: null, due: null, pause_note: null, resume_note: null,
});

describe("groupByStatus", () => {
  it("groups by status and sorts by priority", () => {
    const g = groupByStatus([task("a", "todo", "low"), task("b", "todo", "urgent"), task("c", "on_hold", "medium")]);
    expect(g.todo.map((t) => t.id)).toEqual(["b", "a"]);
    expect(g.on_hold.map((t) => t.id)).toEqual(["c"]);
    expect(g.done).toEqual([]);
  });
});
