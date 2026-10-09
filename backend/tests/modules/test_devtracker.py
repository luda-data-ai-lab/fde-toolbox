from tests.conftest import World


def test_task_flow_and_dashboard(world: World) -> None:
    base = f"/api/v1/t/{world.a.tenant_id}/devtracker"
    fde = world.a.fde
    pid = world.a.ids["project_id"]
    t2 = fde.post(
        f"{base}/projects/{pid}/tasks",
        json={"title": "Late", "due": "2020-01-01", "priority": "high", "assignee_id": world.a.fde_id},
    ).json()
    t3 = fde.post(f"{base}/projects/{pid}/tasks", json={"title": "Done", "status": "done"}).json()
    r = fde.post(f"{base}/tasks/{t2['id']}/pause", json={"pause_note": "stuck on auth", "resume_note": "retry"})
    assert r.json()["status"] == "on_hold" and r.json()["pause_note"] == "stuck on auth"
    dash = fde.get(f"{base}/projects/{pid}/dashboard").json()
    assert dash["total_tasks"] == 3 and dash["status_counts"]["done"] == 1
    assert round(dash["progress"], 2) == 0.33
    assert [t["id"] for t in dash["paused_tasks"]] == [t2["id"]]
    assert [t["id"] for t in dash["overdue_tasks"]] == [t2["id"]]
    assert len(dash["recent_prompts"]) == 1
    assert fde.post(f"{base}/tasks/{t2['id']}/resume").json()["status"] == "in_progress"
    todo = fde.get(f"{base}/projects/{pid}/tasks", params={"status": "todo"}).json()["items"]
    assert [t["title"] for t in todo] == ["Task TA"]
    assert fde.patch(f"{base}/tasks/{t3['id']}", json={"status": "review"}).json()["status"] == "review"
    assert fde.patch(f"{base}/tasks/{t3['id']}", json={"status": "bogus"}).status_code == 422
    assert fde.delete(f"{base}/tasks/{t3['id']}").status_code == 204


def test_prompts_and_projects(world: World) -> None:
    base = f"/api/v1/t/{world.a.tenant_id}/devtracker"
    fde = world.a.fde
    tid = world.a.ids["task_id"]
    p = fde.post(
        f"{base}/tasks/{tid}/prompts", json={"tool": "claude_code", "prompt": "fix it", "result_summary": "done"}
    ).json()
    assert fde.patch(f"{base}/prompts/{p['id']}", json={"result_summary": "ok"}).json()["result_summary"] == "ok"
    assert len(fde.get(f"{base}/tasks/{tid}/prompts").json()["items"]) == 2
    assert fde.delete(f"{base}/prompts/{p['id']}").status_code == 204
    pid = world.a.ids["project_id"]
    assert fde.patch(f"{base}/projects/{pid}", json={"status": "active"}).json()["status"] == "active"
    listed = fde.get(f"{base}/projects", params={"engagement_id": world.a.ids["engagement_id"]}).json()["items"]
    assert [x["id"] for x in listed] == [pid]
    assert fde.delete(f"{base}/projects/{pid}").status_code == 204
    assert fde.get(f"{base}/tasks/{tid}").status_code == 404


def test_home_dashboard(world: World) -> None:
    home = world.a.fde.get("/api/v1/home").json()
    assert home["role"] == "fde" and [t["code"] for t in home["tenants"]] == ["TA"]
    assert home["tenants"][0]["devtracker"]["open_tasks"] == 1
    assert home["tenants"][0]["agenthub"]["instances_by_status"] == {"ready": 1}
    admin_home = world.admin.get("/api/v1/home").json()
    assert admin_home["totals"]["tenants"] == 2 and admin_home["totals"]["assets"] == 4
