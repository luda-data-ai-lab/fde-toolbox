import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";

const RUN = `S${Date.now().toString(36).toUpperCase()}`;
const PASSWORD = "e2e-user-pass-123";

async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("이메일").fill(email);
  await page.getByLabel("비밀번호").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
}

test("FDE assembles Spec.md from DiscoveryQ input, edits, versions, diffs and exports; client user reads only", async ({
  page,
  request,
}) => {
  await request.post("/api/v1/auth/login", { data: { email: "admin@e2e.local", password: "admin-pass-123" } });
  const tenant = (await (
    await request.post("/api/v1/admin/tenants", { data: { name: `SF-${RUN}`, code: RUN } })
  ).json()) as { id: string };
  for (const role of ["fde", "client_user"])
    await request.post("/api/v1/admin/users", {
      data: {
        email: `${role}-${RUN}@e2e.local`,
        name: role,
        role,
        password: PASSWORD,
        ...(role === "fde" ? { tenant_ids: [tenant.id] } : { home_tenant_id: tenant.id }),
      },
    });
  const base = `/api/v1/t/${tenant.id}`;
  const eng = (await (await request.post(`${base}/engagements`, { data: { name: "명세 작성" } })).json()) as {
    id: string;
  };
  const session = (await (
    await request.post(`${base}/discoveryq/sessions`, {
      data: { engagement_id: eng.id, type: "interview", title: "생산팀 인터뷰" },
    })
  ).json()) as { id: string };
  await request.post(`${base}/discoveryq/sessions/${session.id}/insights`, {
    data: { text: "배합 지시서가 엑셀로 관리되어 버전 혼선이 잦다" },
  });

  await login(page, `fde-${RUN}@e2e.local`);
  await page.getByRole("link", { name: "SpecForge" }).click();
  await page.getByLabel("프로젝트(인게이지먼트)").selectOption(eng.id);

  const form = page.getByRole("form", { name: "새 문서 조립" });
  await form.getByLabel("제목").fill("배합 관리 명세");
  await form.getByLabel("생산팀 인터뷰").check();
  await form.getByLabel("자유 입력 요구사항").fill("배합 지시서를 시스템에서 승인한다.");
  await form.getByRole("button", { name: "초안 조립" }).click();

  const editor = page.getByTestId("spec-content");
  const preview = page.getByTestId("spec-preview");
  await expect(page.getByTestId("spec-title")).toHaveText("배합 관리 명세");
  await expect(preview).toContainText("배합 지시서가 엑셀로 관리되어 버전 혼선이 잦다");
  await expect(preview).toContainText("배합 지시서를 시스템에서 승인한다.");

  const versions = page.getByTestId("spec-versions");
  await versions.getByLabel("버전 메모").fill("초안");
  await versions.getByRole("button", { name: "버전 저장" }).click();
  await expect(versions).toContainText("v1");

  await editor.fill(`${await editor.inputValue()}\n## 추가 메모\n\n승인 이력을 남긴다.\n`);
  await expect(preview).toContainText("승인 이력을 남긴다.");
  await page.getByRole("button", { name: "저장", exact: true }).click();
  await expect(page.getByText("저장하지 않은 변경이 있습니다.")).toHaveCount(0);
  await expect(page.getByTestId("spec-diff")).toContainText("+승인 이력을 남긴다.");

  await page.getByTestId("spec-enrich").getByRole("button", { name: "프롬프트 만들기" }).click();
  await expect(page.getByTestId("spec-prompt")).toHaveValue(/승인 이력을 남긴다\./);

  await page.getByRole("button", { name: "확정" }).click();
  await expect(page.getByTestId("spec-editor")).toContainText("확정");

  const md = page.waitForEvent("download");
  await page.getByTestId("spec-export-md").click();
  const download = await md;
  expect(download.suggestedFilename()).toBe("Spec.md");
  const text = await readFile(await download.path(), "utf-8");
  expect(text).toContain("# 배합 관리 명세");
  expect(text).toContain("승인 이력을 남긴다.");

  await page.context().clearCookies();
  await login(page, `client_user-${RUN}@e2e.local`);
  await page.getByRole("link", { name: "SpecForge" }).click();
  await page.getByRole("button", { name: "배합 관리 명세" }).click();
  await expect(page.getByTestId("spec-content")).toHaveAttribute("readonly", "");
  await expect(page.getByRole("button", { name: "저장", exact: true })).toHaveCount(0);
  await expect(page.getByRole("form", { name: "새 문서 조립" })).toHaveCount(0);
  await expect(page.getByTestId("spec-export-md")).toHaveCount(0);
  await expect(page.getByTestId("spec-diff")).toContainText("+승인 이력을 남긴다.");
});
