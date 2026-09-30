import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const ADMIN = { email: "admin@e2e.local", password: "admin-pass-123" };
const PASSWORD = "e2e-user-pass-123";
const RUN = Date.now().toString(36).toUpperCase();

interface Ids {
  tenantA: string;
  tenantB: string;
  instanceName: string;
  templateTitle: string;
}

async function apiLogin(request: APIRequestContext, email: string, password: string) {
  const res = await request.post("/api/v1/auth/login", { data: { email, password } });
  expect(res.ok()).toBeTruthy();
}

async function uiLogin(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("이메일").fill(email);
  await page.getByLabel("비밀번호").fill(password);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page.getByTestId("current-user")).toBeVisible();
}

async function selectTenant(page: Page, name: string) {
  await page.getByLabel("고객사", { exact: true }).selectOption({ label: name });
}

const ids: Ids = { tenantA: "", tenantB: "", instanceName: `A-일보-${RUN}`, templateTitle: `E2E 일보 에이전트 ${RUN}` };

test.describe.serial("Phase 0 acceptance", () => {
  test.beforeAll(async ({ request }) => {
    await apiLogin(request, ADMIN.email, ADMIN.password);
    const mk = async (name: string, code: string) =>
      (await (await request.post("/api/v1/admin/tenants", { data: { name, code } })).json()) as { id: string };
    ids.tenantA = (await mk(`고객사A-${RUN}`, `A${RUN}`)).id;
    ids.tenantB = (await mk(`고객사B-${RUN}`, `B${RUN}`)).id;
    const users = [
      { email: `fde-a-${RUN}@e2e.local`, name: "FDE A", role: "fde", tenant_ids: [ids.tenantA] },
      { email: `fde-b-${RUN}@e2e.local`, name: "FDE B", role: "fde", tenant_ids: [ids.tenantB] },
      { email: `client-b-${RUN}@e2e.local`, name: "Client B", role: "client_admin", home_tenant_id: ids.tenantB },
    ];
    for (const u of users) {
      const res = await request.post("/api/v1/admin/users", { data: { ...u, password: PASSWORD } });
      expect(res.status()).toBe(201);
    }
    for (const [tid, name] of [
      [ids.tenantA, "A 생산 데이터 통합"],
      [ids.tenantB, "B 품질 개선"],
    ] as const) {
      await apiLogin(request, ADMIN.email, ADMIN.password);
      const res = await request.post(`/api/v1/t/${tid}/engagements`, { data: { name } });
      expect(res.status()).toBe(201);
    }
  });

  test("admin registers agent template v1 and v2 with a diff", async ({ page }) => {
    await uiLogin(page, ADMIN.email, ADMIN.password);
    await page.getByRole("link", { name: "자산 라이브러리" }).click();
    const form = page.locator("form").filter({ has: page.getByLabel("자산 키") });
    await form.getByLabel("자산 유형").selectOption("agent_template");
    await form.getByLabel("자산 키").fill(`e2e-daily-${RUN.toLowerCase()}`);
    await form.getByLabel("제목").fill(ids.templateTitle);
    await form.getByLabel("내용(JSON)").fill(JSON.stringify({ purpose: "일보 요약", system_prompt: "v1 프롬프트" }));
    await form.getByRole("button", { name: "등록" }).click();

    await page.getByRole("link", { name: "AgentHub" }).click();
    await page.getByRole("link", { name: ids.templateTitle }).click();
    await expect(page.getByText("v1 프롬프트", { exact: true })).toBeVisible();
    const payload = page.getByLabel("내용(JSON)");
    await payload.fill(JSON.stringify({ purpose: "일보 요약", system_prompt: "v2 프롬프트: 불량률 강조" }, null, 2));
    await page.getByLabel("변경 사유").fill("불량률 강조");
    await page.getByRole("button", { name: "저장" }).click();
    await expect(page.getByRole("button", { name: "v2" })).toBeVisible();
    await expect(page.getByText("+v2 프롬프트: 불량률 강조").first()).toBeVisible();
  });

  test("FDE of tenant A records an instance on template v2", async ({ page }) => {
    await uiLogin(page, `fde-a-${RUN}@e2e.local`, PASSWORD);
    await page.getByRole("link", { name: "AgentHub" }).click();
    const form = page.getByTestId("instance-form");
    await form.getByLabel("이름").fill(ids.instanceName);
    await form.getByLabel("템플릿").selectOption({ label: ids.templateTitle });
    await form.getByLabel("버전").selectOption("2");
    await form.getByLabel("프로젝트(인게이지먼트)").selectOption({ label: "A 생산 데이터 통합" });
    await form.getByRole("button", { name: "등록" }).click();
    const row = page.getByTestId("instances-table").getByRole("row", { name: new RegExp(ids.instanceName) });
    await expect(row).toContainText(`${ids.templateTitle} v2`);
  });

  for (const who of ["fde-b", "client-b"]) {
    test(`${who} (tenant B) cannot see tenant A's instance`, async ({ page }) => {
      await uiLogin(page, `${who}-${RUN}@e2e.local`, PASSWORD);
      const tenants = await page.getByLabel("고객사", { exact: true }).locator("option").allTextContents();
      expect(tenants).toEqual([`고객사B-${RUN}`]);
      await page.getByRole("link", { name: "AgentHub" }).click();
      await expect(page.getByText("데이터가 없습니다.").last()).toBeVisible();
      await expect(page.getByText(ids.instanceName)).toHaveCount(0);

      const list = await page.request.get(`/api/v1/t/${ids.tenantA}/agenthub/instances`);
      expect(list.status()).toBe(404);
      const home = await (await page.request.get("/api/v1/home")).text();
      expect(home).not.toContain(ids.instanceName);
      expect(home).not.toContain(ids.tenantA);
    });
  }

  test("tenant A FDE sees the instance on home and can switch tenants only within assignment", async ({ page }) => {
    await uiLogin(page, `fde-a-${RUN}@e2e.local`, PASSWORD);
    await selectTenant(page, `고객사A-${RUN}`);
    await expect(page.getByTestId(`home-tenant-A${RUN}`)).toBeVisible();
    await expect(page.getByTestId(`home-tenant-B${RUN}`)).toHaveCount(0);
  });
});
