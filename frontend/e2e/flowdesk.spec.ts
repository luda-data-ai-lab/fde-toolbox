import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

const RUN = `F${Date.now().toString(36).toUpperCase()}`;
const PASSWORD = "e2e-user-pass-123";

test("FDE starts a flow from a template, links a system, snapshots, pairs a To-Be and exports", async ({
  page,
  request,
}) => {
  await request.post("/api/v1/auth/login", { data: { email: "admin@e2e.local", password: "admin-pass-123" } });
  const tenant = (await (
    await request.post("/api/v1/admin/tenants", { data: { name: `FD-${RUN}`, code: RUN } })
  ).json()) as { id: string };
  await request.post("/api/v1/admin/users", {
    data: { email: `fde-${RUN}@e2e.local`, name: "FDE", role: "fde", password: PASSWORD, tenant_ids: [tenant.id] },
  });
  const base = `/api/v1/t/${tenant.id}`;
  const eng = (await (await request.post(`${base}/engagements`, { data: { name: "흐름 설계" } })).json()) as {
    id: string;
  };
  await request.post(`${base}/systems`, { data: { name: "생산관리 MES", short_name: "MES", type: "MES" } });

  await page.goto("/login");
  await page.getByLabel("이메일").fill(`fde-${RUN}@e2e.local`);
  await page.getByLabel("비밀번호").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await page.getByRole("link", { name: "FlowDesk" }).click();
  await page.getByLabel("프로젝트(인게이지먼트)").selectOption(eng.id);

  const form = page.getByRole("form", { name: "새 흐름" });
  await form.getByLabel("제목").fill("수주 출하 As-Is");
  await form.getByLabel("템플릿").selectOption({ label: "도료 제조 수주→생산→출하 (v1)" });
  await form.getByRole("button", { name: "등록" }).click();

  const nodes = page.getByTestId("flow-node");
  await expect(nodes).toHaveCount(11);
  await nodes.filter({ hasText: "수주 접수" }).click();
  const panel = page.getByTestId("node-panel");
  await panel.getByLabel("이름", { exact: true }).fill("수주 접수(ERP)");
  await panel
    .locator("label", { hasText: /^시스템/ })
    .locator("select")
    .selectOption({ label: "생산관리 MES" });
  await page.getByRole("button", { name: "저장", exact: true }).click();
  await expect(page.getByRole("button", { name: "저장됨" })).toBeVisible();

  const snaps = page.getByTestId("snapshots");
  await snaps.getByLabel("스냅샷 메모").fill("인터뷰 직후");
  await snaps.getByRole("button", { name: "스냅샷 저장" }).click();
  await expect(snaps).toContainText("v1 · 인터뷰 직후");

  const mmd = page.waitForEvent("download");
  await page.getByRole("link", { name: "Mermaid" }).click();
  const mmdText = await readFile(await (await mmd).path(), "utf-8");
  expect(mmdText).toContain("flowchart LR");
  expect(mmdText).toContain('subgraph lane0["영업"]');
  expect(mmdText).toContain("수주 접수(ERP)");

  const json = page.waitForEvent("download");
  await page.getByRole("link", { name: "JSON" }).click();
  const doc = JSON.parse(await readFile(await (await json).path(), "utf-8")) as {
    graph: { nodes: { label: string; system_id: string | null }[] };
  };
  expect(doc.graph.nodes.find((n) => n.label === "수주 접수(ERP)")?.system_id).toBeTruthy();

  const svg = page.waitForEvent("download");
  await page.getByRole("button", { name: "SVG" }).click();
  expect((await svg).suggestedFilename()).toMatch(/\.svg$/);

  await page.getByRole("button", { name: "To-Be 만들기" }).click();
  await expect(page.getByRole("button", { name: "As-Is 열기" })).toBeVisible();
  await expect(page.getByLabel("제목")).toHaveValue("수주 출하 As-Is (To-Be)");
  await expect(nodes).toHaveCount(11);
});
