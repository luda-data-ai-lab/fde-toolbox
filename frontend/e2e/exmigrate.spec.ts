import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { zipText } from "./zip";

const RUN = `X${Date.now().toString(36).toUpperCase()}`;
const PASSWORD = "e2e-user-pass-123";
const SAMPLE = join(process.cwd(), "..", "backend", "seeds", "samples", "interfaces-sample.xlsx");

test("FDE analyzes a workbook, confirms the ERD and downloads migration scripts", async ({ page, request }) => {
  await request.post("/api/v1/auth/login", { data: { email: "admin@e2e.local", password: "admin-pass-123" } });
  const tenant = (await (
    await request.post("/api/v1/admin/tenants", { data: { name: `XM-${RUN}`, code: RUN } })
  ).json()) as { id: string };
  await request.post("/api/v1/admin/users", {
    data: { email: `fde-${RUN}@e2e.local`, name: "FDE", role: "fde", password: PASSWORD, tenant_ids: [tenant.id] },
  });
  const eng = (await (
    await request.post(`/api/v1/t/${tenant.id}/engagements`, { data: { name: "엑셀 이관" } })
  ).json()) as { id: string };

  await page.goto("/login");
  await page.getByLabel("이메일").fill(`fde-${RUN}@e2e.local`);
  await page.getByLabel("비밀번호").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await page.getByRole("link", { name: "ExMigrate 엑셀 분석" }).click();
  await page.getByLabel("프로젝트(인게이지먼트)").selectOption(eng.id);
  await page.getByLabel("엑셀 파일(.xlsx, .xlsm)").setInputFiles(SAMPLE);
  await page.getByRole("button", { name: "업로드·분석" }).click();

  await expect(page.getByTestId("xl-filename")).toHaveText("interfaces-sample.xlsx");
  const sheets = page.getByTestId("xl-sheet");
  await expect(sheets).toHaveCount(2);
  await expect(sheets.first()).toContainText("인터페이스 리스트");
  await expect(sheets.first()).toContainText("송신 시스템");

  await page.getByRole("tab", { name: "스크립트" }).click();
  await expect(page.getByText("ERD를 확정하면 DDL과 적재 스크립트를 만들 수 있습니다.")).toBeVisible();

  await page.getByRole("tab", { name: "ERD" }).click();
  await expect(page.getByTestId("erd-table")).toHaveCount(2);
  const table = page.getByLabel("테이블 이름").first();
  await table.fill("interfaces");
  await page.getByRole("button", { name: "ERD 저장" }).click();
  await expect(page.getByRole("button", { name: "저장됨" })).toBeVisible();
  await page.getByRole("button", { name: "ERD 확정" }).click();
  await expect(page.getByTestId("erd-status")).toHaveText("확정됨");

  await page.getByRole("tab", { name: "스크립트" }).click();
  await expect(page.getByTestId("ddl-preview")).toContainText('CREATE TABLE "interfaces"');
  await page.getByLabel("대상 DB").selectOption("mssql");
  await expect(page.getByTestId("ddl-preview")).toContainText("CREATE TABLE [interfaces]");

  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "스크립트 ZIP 내려받기" }).click();
  const zip = await readFile(await (await download).path());
  expect(zipText(zip, "schema.sql")).toContain("CREATE TABLE [시스템_연동정보]");
  expect(zipText(zip, "mapping.json")).toContain("인터페이스 리스트");
  expect(zipText(zip, "load.py")).toContain("def connect(dialect, url)");

  await page.getByRole("button", { name: "목록으로" }).click();
  await expect(page.getByTestId("xl-list")).toContainText("확정됨");
});
