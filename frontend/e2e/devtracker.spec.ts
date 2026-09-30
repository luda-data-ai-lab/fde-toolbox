import { expect, test } from "@playwright/test";

const RUN = `D${Date.now().toString(36).toUpperCase()}`;
const PASSWORD = "e2e-user-pass-123";

test("FDE runs a DevTracker project: task, pause/resume, prompt log", async ({ page, request }) => {
  await request.post("/api/v1/auth/login", { data: { email: "admin@e2e.local", password: "admin-pass-123" } });
  const tenant = (await (await request.post("/api/v1/admin/tenants", { data: { name: `DT-${RUN}`, code: RUN } })).json()) as { id: string };
  await request.post("/api/v1/admin/users", {
    data: { email: `fde-${RUN}@e2e.local`, name: "FDE", role: "fde", password: PASSWORD, tenant_ids: [tenant.id] },
  });
  await request.post(`/api/v1/t/${tenant.id}/engagements`, { data: { name: "DT 과제" } });

  await page.goto("/login");
  await page.getByLabel("이메일").fill(`fde-${RUN}@e2e.local`);
  await page.getByLabel("비밀번호").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await page.getByRole("link", { name: "DevTracker" }).click();

  const form = page.locator("form").filter({ has: page.getByLabel("기술 스택") });
  await form.getByLabel("프로젝트(인게이지먼트)").selectOption({ label: "DT 과제" });
  await form.getByLabel("이름").fill("일보 자동화");
  await form.getByLabel("기술 스택").fill("FastAPI");
  await form.getByRole("button", { name: "등록" }).click();
  await page.getByRole("link", { name: "일보 자동화" }).click();

  await page.getByLabel("제목").fill("MES 조회 쿼리 작성");
  await page.getByRole("button", { name: "태스크 추가" }).click();
  await page.getByTestId("kanban").getByRole("button", { name: /MES 조회 쿼리 작성/ }).click();
  const panel = page.getByTestId("task-panel");
  await panel.getByLabel("중단 메모").fill("DB 계정 발급 대기");
  await panel.getByLabel("재개 메모").fill("계정 받으면 뷰 권한 확인");
  await panel.getByRole("button", { name: "작업 중단" }).click();
  await expect(page.getByTestId("kanban")).toContainText("DB 계정 발급 대기");

  await panel.getByPlaceholder("프롬프트", { exact: true }).fill("MES 생산실적 테이블 조회 쿼리를 작성해줘");
  await panel.getByPlaceholder("결과 요약").fill("초안 쿼리 생성");
  await panel.getByRole("button", { name: "프롬프트 기록" }).click();
  await expect(panel).toContainText("MES 생산실적 테이블 조회 쿼리를 작성해줘");

  await panel.getByRole("button", { name: "작업 재개" }).click();
  await page.getByRole("button", { name: "목록" }).click();
  await expect(page.getByRole("row", { name: /MES 조회 쿼리 작성/ })).toContainText("진행 중");
  await expect(page.getByTestId("project-dashboard")).toContainText("MES 생산실적");
});
