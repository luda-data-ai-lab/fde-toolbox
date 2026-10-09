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


def test_issues_crud_and_agenthub_source(world: World) -> None:
    base = f"/api/v1/t/{world.a.tenant_id}/devtracker"
    fde = world.a.fde
    pid = world.a.ids["project_id"]
    iid = world.a.ids["instance_id"]
    issues = fde.get(f"{base}/projects/{pid}/issues").json()["items"]
    assert [x["title"] for x in issues] == ["Issue TA"]
    assert issues[0]["source"] == {"module": "agenthub", "instance_id": iid, "note": None}
    created = fde.post(
        f"{base}/projects/{pid}/issues",
        json={"title": "Wrong answer", "kind": "improvement", "priority": "high", "description": "d"},
    )
    assert created.status_code == 201 and created.json()["status"] == "open"
    issue = created.json()
    r = fde.patch(f"{base}/issues/{issue['id']}", json={"status": "resolved"})
    assert r.json()["status"] == "resolved"
    assert fde.patch(f"{base}/issues/{issue['id']}", json={"kind": "bogus"}).status_code == 422
    resolved = fde.get(f"{base}/projects/{pid}/issues", params={"status": "resolved"}).json()["items"]
    assert [x["id"] for x in resolved] == [issue["id"]]
    foreign = {"module": "agenthub", "instance_id": world.b.ids["instance_id"]}
    r = fde.post(f"{base}/projects/{pid}/issues", json={"title": "x", "source": foreign})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_reference"
    assert world.a.client_user.post(f"{base}/projects/{pid}/issues", json={"title": "x"}).status_code == 403
    assert world.a.client_user.get(f"{base}/issues/{issue['id']}").status_code == 200
    assert fde.delete(f"{base}/issues/{issue['id']}").status_code == 204


def test_project_links_only_confirmed_spec_documents(world: World) -> None:
    t = world.a.tenant_id
    fde = world.a.fde
    eid = world.a.ids["engagement_id"]
    doc = world.a.ids["document_id"]
    projects = f"/api/v1/t/{t}/devtracker/projects"
    body = {"engagement_id": eid, "name": "From spec", "spec_document_ids": [doc]}
    r = fde.post(projects, json=body)
    assert r.status_code == 422 and r.json()["error"]["detail"]["field"] == "spec_document_ids"
    assert fde.patch(f"/api/v1/t/{t}/specforge/documents/{doc}", json={"status": "confirmed"}).status_code == 200
    r = fde.post(projects, json={**body, "spec_document_ids": [doc, doc]})
    assert r.status_code == 201 and r.json()["spec_document_ids"] == [doc]
    foreign = fde.post(projects, json={**body, "spec_document_ids": [world.b.ids["document_id"]]})
    assert foreign.status_code == 422
    assert fde.patch(f"{projects}/{r.json()['id']}", json={"spec_document_ids": []}).json()["spec_document_ids"] == []
