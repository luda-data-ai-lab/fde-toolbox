import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

const RUN = `O${Date.now().toString(36).toUpperCase()}`;
const PASSWORD = "e2e-user-pass-123";
const ANSWER = "배합지시서를 받아 칭량 후 LOT 번호를 기록합니다.";

test("FDE registers terms from an interview, confirms them and exports the glossary", async ({
  page,
  request,
}) => {
  await request.post("/api/v1/auth/login", {
    data: { email: "admin@e2e.local", password: "admin-pass-123" },
  });
  const tenant = (await (
    await request.post("/api/v1/admin/tenants", {
      data: { name: `OM-${RUN}`, code: RUN },
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
  const eng = (await (
    await request.post(`${base}/engagements`, { data: { name: "용어 진단" } })
  ).json()) as { id: string };
  const subject = (await (
    await request.post(`${base}/coachq/subjects`, {
      data: { engagement_id: eng.id, name: "박생산", department: "생산팀" },
    })
  ).json()) as { id: string };
  const session = (await (
    await request.post(`${base}/coachq/sessions`, {
      data: {
        engagement_id: eng.id,
        subject_id: subject.id,
        title: "생산 용어 인터뷰",
      },
    })
  ).json()) as { id: string };
  await request.post(`${base}/coachq/sessions/${session.id}/questions`, {
    data: { custom_text: "작업 지시는 어떻게 받나요?" },
  });

  await page.goto("/login");
  await page.getByLabel("이메일").fill(`fde-${RUN}@e2e.local`);
  await page.getByLabel("비밀번호").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await page.getByRole("link", { name: "CoachQ" }).click();
  await page.goto(`/coachq?tab=sessions&session=${session.id}`);

  const card = page.getByTestId("worksheet-question");
  const answer = card.getByLabel("답변");
  await answer.fill(ANSWER);
  await answer.press("Control+Home");
  for (let i = 0; i < 5; i++) await answer.press("Shift+ArrowRight");
  const termInput = card.getByLabel("용어 후보");
  await expect(termInput).toHaveValue("배합지시서");
  const register = card.getByRole("button", { name: "용어로 등록" });
  await register.click();
  await expect(card.getByRole("status")).toContainText("후보로 등록됨");
  for (const name of ["칭량", "LOT 번호"]) {
    await termInput.fill(name);
    await register.click();
    await expect(termInput).toHaveValue("");
  }
  const listed = page.getByTestId("session-terms");
  for (const name of ["배합지시서", "칭량", "LOT 번호"])
    await expect(listed).toContainText(name);

  await page.getByRole("link", { name: "OntoMap 용어 사전" }).click();
  await page.getByRole("tab", { name: "후보" }).click();
  const rows = page.getByTestId("candidate-row");
  await expect(rows).toHaveCount(3);
  await expect(rows.first()).toContainText("생산팀");
  for (let i = 0; i < 3; i++) {
    await rows.first().getByRole("button", { name: "확정" }).click();
    await expect(rows).toHaveCount(2 - i);
  }

  await page.getByRole("tab", { name: "용어 사전" }).click();
  const terms = page.getByTestId("term-row");
  await expect(terms).toHaveCount(3);
  await expect(terms.filter({ hasText: "칭량" })).toContainText("확정");
  await expect(terms.filter({ hasText: "칭량" })).toContainText("생산팀: 칭량");

  const csv = page.waitForEvent("download");
  await page.getByRole("link", { name: "CSV 내보내기" }).click();
  const csvText = await readFile(await (await csv).path(), "utf-8");
  expect(csvText).toContain(
    "표준 용어,정의,부서별 호칭,약어,관련 개념,비고,상태",
  );
  expect(csvText).toContain("칭량,,생산팀: 칭량,,,,확정");
  const xlsx = page.waitForEvent("download");
  await page.getByRole("link", { name: "엑셀 내보내기" }).click();
  expect((await xlsx).suggestedFilename()).toBe("glossary.xlsx");
});
