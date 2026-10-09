import { expect, test } from "@playwright/test";

const RUN = `P2${Date.now().toString(36).toUpperCase()}`;
const PASSWORD = "e2e-user-pass-123";

const ANSWER = {
  lanes: ["영업", "생산"],
  nodes: [
    { id: "n1", type: "start", label: "주문 시작", lane: "영업" },
    { id: "n2", type: "task", label: "주문 등록", lane: "영업" },
    { id: "n3", type: "end", label: "생산 지시", lane: "생산" },
  ],
  edges: [
    { source: "n1", target: "n2" },
    { source: "n2", target: "n3" },
  ],
};

test("Phase 2 acceptance: insight → flow → Spec.md → DevTracker project, offline (prompt copy)", async ({
  page,
  request,
}) => {
  await request.post("/api/v1/auth/login", { data: { email: "admin@e2e.local", password: "admin-pass-123" } });
  const tenant = (await (
    await request.post("/api/v1/admin/tenants", { data: { name: `P2-${RUN}`, code: RUN } })
  ).json()) as { id: string };
  await request.post("/api/v1/admin/users", {
    data: { email: `fde-${RUN}@e2e.local`, name: "FDE", role: "fde", password: PASSWORD, tenant_ids: [tenant.id] },
  });
  const base = `/api/v1/t/${tenant.id}`;
  const eng = (await (await request.post(`${base}/engagements`, { data: { name: "수주 개선" } })).json()) as {
    id: string;
  };
  const session = (await (
    await request.post(`${base}/discoveryq/sessions`, { data: { engagement_id: eng.id, title: "영업팀 인터뷰" } })
  ).json()) as { id: string };
  await request.post(`${base}/discoveryq/sessions/${session.id}/insights`, {
    data: { text: "수주를 메일로 받아 ERP에 두 번 입력한다" },
  });

  await page.goto("/login");
  await page.getByLabel("이메일").fill(`fde-${RUN}@e2e.local`);
  await page.getByLabel("비밀번호").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page.getByRole("link", { name: "FlowDesk" })).toBeVisible();

  // DiscoveryQ → FlowDesk
  await page.goto(`/discoveryq?session=${session.id}`);
  await page.getByTestId("send-flowdesk").click();
  const gen = page.getByRole("region", { name: "흐름 생성(프롬프트·LLM)" });
  await expect(gen.getByTestId("gen-insights").getByLabel(/두 번 입력/)).toBeChecked();
  await gen.getByLabel("제목").fill("수주 처리 As-Is");
  await gen.getByRole("button", { name: "프롬프트 만들기" }).click();
  await expect(gen.getByRole("textbox", { name: "프롬프트", exact: true })).toHaveValue(/두 번 입력/);
  await expect(gen.getByRole("button", { name: "LLM으로 자동 생성" })).toHaveCount(0);
  await gen.getByRole("textbox", { name: "LLM 결과 붙여넣기" }).fill(JSON.stringify(ANSWER));
  await gen.getByRole("button", { name: "결과로 흐름 만들기" }).click();
  await expect(page.getByTestId("flow-node")).toHaveCount(3);

  // FlowDesk → SpecForge
  await page.getByTestId("send-specforge").click();
  const form = page.getByRole("form", { name: "새 문서 조립" });
  await expect(form.getByLabel("수주 처리 As-Is")).toBeChecked();
  await form.getByLabel("영업팀 인터뷰").check();
  await form.getByLabel("제목").fill("수주 개선 명세");
  await form.getByRole("button", { name: "초안 조립" }).click();
  const preview = page.getByTestId("spec-preview");
  await expect(page.getByTestId("spec-title")).toHaveText("수주 개선 명세");
  await expect(preview).toContainText("주요 단계: 주문 등록");
  await expect(preview).toContainText("수주를 메일로 받아 ERP에 두 번 입력한다");
  await expect(page.getByTestId("send-devtracker")).toHaveCount(0);

  const versions = page.getByTestId("spec-versions");
  await versions.getByLabel("버전 메모").fill("인수 초안");
  await versions.getByRole("button", { name: "버전 저장" }).click();
  await expect(versions).toContainText("v1");
  await page.getByRole("button", { name: "확정" }).click();
  await expect(page.getByTestId("spec-editor")).toContainText("확정");

  // SpecForge → DevTracker
  await page.getByTestId("send-devtracker").click();
  const project = page.getByTestId("project-form");
  await expect(project.getByTestId("project-from-spec")).toBeVisible();
  await expect(project.getByLabel("이름")).toHaveValue("수주 개선 명세");
  await project.getByRole("button", { name: "등록" }).click();
  const linked = page.getByTestId("linked-specs");
  await expect(linked).toContainText("수주 개선 명세 (Spec.md)");
  await linked.getByRole("link", { name: /수주 개선 명세/ }).click();
  await expect(page.getByTestId("spec-title")).toHaveText("수주 개선 명세");

  const projects = (await (
    await page.request.get(`${base}/devtracker/projects`, { params: { engagement_id: eng.id } })
  ).json()) as { items: { spec_document_ids: string[] }[] };
  expect(projects.items).toHaveLength(1);
  expect(projects.items[0]?.spec_document_ids).toHaveLength(1);
});
