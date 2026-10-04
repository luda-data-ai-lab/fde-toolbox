import { expect, test } from "@playwright/test";
import { join } from "node:path";
import { readFile } from "node:fs/promises";
import { zipText } from "./zip";

const RUN = `P${Date.now().toString(36).toUpperCase()}`;
const PASSWORD = "e2e-user-pass-123";
const SAMPLE = join(
  process.cwd(),
  "..",
  "backend",
  "seeds",
  "samples",
  "interfaces-sample.xlsx",
);
const ANSWER = "배합지시서에 따라 원료를 칭량하고 점도 규격을 확인합니다.";
const TERMS = ["배합지시서", "칭량", "점도 규격"];

test("Phase 1 acceptance: I/F workbook → graph, interview → 3 terms → confirm → glossary Excel", async ({
  page,
  request,
}) => {
  await request.post("/api/v1/auth/login", {
    data: { email: "admin@e2e.local", password: "admin-pass-123" },
  });
  const tenant = (await (
    await request.post("/api/v1/admin/tenants", {
      data: { name: `P1-${RUN}`, code: RUN },
    })
  ).json()) as { id: string };
  await request.post("/api/v1/admin/users", {
    data: {
      email: `fde-${RUN}@e2e.local`,
      name: "FDE",
      role: "fde",
      password: PASSWORD,
      tenant_ids: [tenant.id],
    },
  });
  const base = `/api/v1/t/${tenant.id}`;
  for (const name of ["ERP", "MES"])
    expect(
      (
        await request.post(`${base}/systems`, { data: { name, type: name } })
      ).status(),
    ).toBe(201);
  await request.post(`${base}/engagements`, {
    data: { name: "도료 공정 진단" },
  });

  await page.goto("/login");
  await page.getByLabel("이메일").fill(`fde-${RUN}@e2e.local`);
  await page.getByLabel("비밀번호").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();

  await page.getByRole("link", { name: "I/F 관리" }).click();
  await page.getByRole("tab", { name: "엑셀 업로드" }).click();
  await page.getByLabel("I/F 엑셀 파일").setInputFiles(SAMPLE);
  await expect(page.getByTestId("upload-summary")).toContainText("전체 행15");
  await page.getByRole("button", { name: "반영" }).click();
  await expect(page.getByTestId("upload-applied")).toHaveText(
    "반영 완료: 신규 15건, 갱신 0건, 건너뜀 0건, 시스템 등록 4건",
  );
  await page.getByRole("tab", { name: "연결 그래프" }).click();
  await expect(page.getByTestId("graph-node")).toHaveCount(6);
  await expect(page.getByTestId("graph-edge")).toHaveCount(11);
  await page.getByTestId("graph-node").filter({ hasText: "GW" }).click();
  await expect(page.getByTestId("graph-selection")).toContainText("IF-ERP-002");

  await page.getByRole("link", { name: "DiscoveryQ" }).click();
  await page.getByRole("tab", { name: "대상자" }).click();
  const subjectForm = page.getByRole("form", { name: "대상자 등록" });
  await subjectForm
    .getByLabel("프로젝트(인게이지먼트)")
    .selectOption({ label: "도료 공정 진단" });
  await subjectForm.getByLabel("이름").fill("박생산");
  await subjectForm.getByLabel("부서").fill("생산팀");
  await subjectForm.getByRole("button", { name: "등록" }).click();
  await expect(page.getByTestId("subject-table")).toContainText("박생산");

  await page.getByRole("tab", { name: "세션" }).click();
  const sessionForm = page.getByRole("form", { name: "새 세션" });
  await sessionForm
    .getByLabel("프로젝트(인게이지먼트)")
    .selectOption({ label: "도료 공정 진단" });
  await sessionForm
    .getByLabel("인터뷰 대상자")
    .selectOption({ label: "박생산" });
  await sessionForm.getByLabel("제목").fill("배합 공정 인터뷰");
  await sessionForm.getByLabel("일자").fill("2026-10-01");
  await sessionForm.getByRole("button", { name: "등록" }).click();
  await expect(page.getByTestId("worksheet")).toContainText("배합 공정 인터뷰");
  await page
    .getByLabel("직접 질문 입력")
    .fill("배합 작업은 어떻게 진행하나요?");
  await page
    .locator("form")
    .filter({ has: page.getByLabel("직접 질문 입력") })
    .getByRole("button", { name: "추가" })
    .click();

  const card = page.getByTestId("worksheet-question");
  await expect(card).toHaveCount(1);
  const answer = card.getByLabel("답변");
  await answer.fill(ANSWER);
  await card.getByLabel("인사이트").click();
  await expect(card).toContainText("저장됨");
  await answer.press("Control+Home");
  for (let i = 0; i < TERMS[0].length; i++)
    await answer.press("Shift+ArrowRight");
  const termInput = card.getByLabel("용어 후보");
  await expect(termInput).toHaveValue(TERMS[0]);
  const register = card.getByRole("button", { name: "용어로 등록" });
  await register.click();
  await expect(card.getByRole("status")).toContainText("후보로 등록됨");
  for (const name of TERMS.slice(1)) {
    await termInput.fill(name);
    await register.click();
    await expect(termInput).toHaveValue("");
  }
  for (const name of TERMS)
    await expect(page.getByTestId("session-terms")).toContainText(name);

  await page.getByRole("link", { name: "OntoMap 용어 사전" }).click();
  await page.getByRole("tab", { name: "후보" }).click();
  const rows = page.getByTestId("candidate-row");
  await expect(rows).toHaveCount(3);
  for (let i = 0; i < 3; i++) {
    await rows.first().getByRole("button", { name: "확정" }).click();
    await expect(rows).toHaveCount(2 - i);
  }
  await page.getByRole("tab", { name: "용어 사전" }).click();
  const terms = page.getByTestId("term-row");
  await expect(terms).toHaveCount(3);
  for (const name of TERMS)
    await expect(terms.filter({ hasText: name })).toContainText("확정");

  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "엑셀 내보내기" }).click();
  const xlsx = await download;
  expect(xlsx.suggestedFilename()).toBe("glossary.xlsx");
  const strings = zipText(await readFile(await xlsx.path()), "xl/");
  for (const name of [...TERMS, "생산팀: 칭량", "확정"])
    expect(strings).toContain(name);
});
