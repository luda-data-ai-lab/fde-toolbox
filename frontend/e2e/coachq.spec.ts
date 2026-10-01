import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

const RUN = `C${Date.now().toString(36).toUpperCase()}`;
const PASSWORD = "e2e-user-pass-123";
const Q1 = "현재 이 업무는 어떤 순서로 진행되나요?";

test("FDE records an interview worksheet and exports it", async ({ page, request }) => {
  await request.post("/api/v1/auth/login", { data: { email: "admin@e2e.local", password: "admin-pass-123" } });
  const tenant = (await (
    await request.post("/api/v1/admin/tenants", { data: { name: `CQ-${RUN}`, code: RUN } })
  ).json()) as { id: string };
  await request.post("/api/v1/admin/users", {
    data: { email: `fde-${RUN}@e2e.local`, name: "FDE", role: "fde", password: PASSWORD, tenant_ids: [tenant.id] },
  });
  await request.post(`/api/v1/t/${tenant.id}/engagements`, { data: { name: "CQ 진단" } });

  await page.goto("/login");
  await page.getByLabel("이메일").fill(`fde-${RUN}@e2e.local`);
  await page.getByLabel("비밀번호").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await page.getByRole("link", { name: "CoachQ" }).click();

  await page.getByRole("tab", { name: "질문 뱅크" }).click();
  await expect(page.locator("[data-testid^='bank-']")).toHaveCount(8);
  await page.getByLabel("세션 유형").selectOption({ label: "현장 인터뷰" });
  await expect(page.locator("[data-testid^='bank-']")).toHaveCount(4);

  await page.getByRole("tab", { name: "대상자" }).click();
  const subjectForm = page.getByRole("form", { name: "대상자 등록" });
  await subjectForm.getByLabel("프로젝트(인게이지먼트)").selectOption({ label: "CQ 진단" });
  await subjectForm.getByLabel("이름").fill("김생산");
  await subjectForm.getByLabel("부서").fill("생산팀");
  await subjectForm.getByRole("button", { name: "등록" }).click();
  await expect(page.getByTestId("subject-table")).toContainText("김생산");

  await page.getByRole("tab", { name: "세션" }).click();
  const sessionForm = page.getByRole("form", { name: "새 세션" });
  await sessionForm.getByLabel("프로젝트(인게이지먼트)").selectOption({ label: "CQ 진단" });
  await sessionForm.getByLabel("인터뷰 대상자").selectOption({ label: "김생산" });
  await sessionForm.getByLabel("제목").fill("생산팀 현황 인터뷰");
  await sessionForm.getByLabel("일자").fill("2026-10-01");
  await sessionForm.getByRole("button", { name: "등록" }).click();

  const worksheet = page.getByTestId("worksheet");
  await expect(worksheet).toContainText("생산팀 현황 인터뷰");
  await page.getByRole("button", { name: `추가: ${Q1}` }).click();
  await page.getByLabel("직접 질문 입력").fill("MES 실적 마감은 언제 하나요?");
  await page.locator("form").filter({ has: page.getByLabel("직접 질문 입력") }).getByRole("button", { name: "추가" }).click();
  const questions = page.getByTestId("worksheet-question");
  await expect(questions).toHaveCount(2);

  const first = questions.first();
  await first.getByLabel("답변").fill("ERP에서 지시를 받고 MES에 실적을 입력합니다.");
  await first.getByLabel("인사이트").click();
  await expect(first).toContainText("저장됨");
  await first.getByLabel("인사이트").fill("실적 이중 입력");
  await first.getByLabel("태그").fill("pain, mes");
  await first.getByRole("button", { name: "인사이트 추가" }).click();
  await expect(first).toContainText("실적 이중 입력 #pain #mes");

  const actionForm = page.getByRole("form", { name: "액션 아이템 추가" });
  await actionForm.getByLabel("액션 아이템").fill("MES 실적 테이블 확인");
  await actionForm.getByLabel("담당자").fill("김대리");
  await actionForm.getByLabel("기한").fill("2026-10-15");
  await actionForm.getByLabel("인사이트").selectOption({ label: "실적 이중 입력" });
  await actionForm.getByRole("button", { name: "액션 추가" }).click();
  const row = page.getByTestId("action-row");
  await expect(row).toContainText("MES 실적 테이블 확인");
  await row.getByLabel("상태").selectOption({ label: "진행 중" });
  await expect(row.getByLabel("상태")).toHaveValue("in_progress");

  const md = page.waitForEvent("download");
  await page.getByRole("link", { name: "Markdown 내보내기" }).click();
  const mdText = await readFile(await (await md).path(), "utf-8");
  expect(mdText).toContain("# 생산팀 현황 인터뷰");
  expect(mdText).toContain("> ERP에서 지시를 받고 MES에 실적을 입력합니다.");
  expect(mdText).toContain("| MES 실적 테이블 확인 | 김대리 | 2026-10-15 | 진행 중 |");

  await page.getByRole("button", { name: "목록으로" }).click();
  await page.getByRole("tab", { name: "액션 아이템" }).click();
  await expect(page.getByTestId("action-row")).toHaveCount(1);
  const csv = page.waitForEvent("download");
  await page.getByRole("link", { name: "액션 아이템 CSV" }).click();
  const csvText = await readFile(await (await csv).path(), "utf-8");
  expect(csvText).toContain("생산팀 현황 인터뷰,2026-10-01,MES 실적 테이블 확인,김대리,2026-10-15,진행 중,실적 이중 입력");
});
