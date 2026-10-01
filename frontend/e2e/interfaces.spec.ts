import { expect, test } from "@playwright/test";
import { join } from "node:path";

const RUN = `I${Date.now().toString(36).toUpperCase()}`;
const PASSWORD = "e2e-user-pass-123";
const SAMPLE = join(
  process.cwd(),
  "..",
  "backend",
  "seeds",
  "samples",
  "interfaces-sample.xlsx",
);

test("FDE uploads the I/F workbook, registers systems and reviews the graph", async ({
  page,
  request,
}) => {
  await request.post("/api/v1/auth/login", {
    data: { email: "admin@e2e.local", password: "admin-pass-123" },
  });
  const tenant = (await (
    await request.post("/api/v1/admin/tenants", {
      data: { name: `IF-${RUN}`, code: RUN },
    })
  ).json()) as {
    id: string;
  };
  await request.post("/api/v1/admin/users", {
    data: {
      email: `fde-${RUN}@e2e.local`,
      name: "FDE",
      role: "fde",
      password: PASSWORD,
      tenant_ids: [tenant.id],
    },
  });
  for (const [name, type] of [
    ["ERP", "ERP"],
    ["MES", "MES"],
  ]) {
    expect(
      (
        await request.post(`/api/v1/t/${tenant.id}/systems`, {
          data: { name, type },
        })
      ).status(),
    ).toBe(201);
  }

  await page.goto("/login");
  await page.getByLabel("이메일").fill(`fde-${RUN}@e2e.local`);
  await page.getByLabel("비밀번호").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await page.getByRole("link", { name: "I/F 관리" }).click();

  await page.getByRole("tab", { name: "엑셀 업로드" }).click();
  await page.getByLabel("I/F 엑셀 파일").setInputFiles(SAMPLE);
  const summary = page.getByTestId("upload-summary");
  await expect(summary).toContainText("전체 행15");
  const unregistered = page.getByTestId("unregistered-systems");
  for (const name of ["LIMS", "WMS", "SCADA", "그룹웨어"])
    await expect(unregistered).toContainText(name);
  await unregistered.getByLabel(/그룹웨어/).uncheck();
  await page.getByRole("button", { name: "반영" }).click();
  await expect(page.getByTestId("upload-applied")).toHaveText(
    "반영 완료: 신규 13건, 갱신 0건, 건너뜀 2건, 시스템 등록 3건",
  );

  await page.getByRole("tab", { name: "연결 그래프" }).click();
  await expect(page.getByTestId("graph-node")).toHaveCount(5);
  await expect(page.getByTestId("graph-edge")).toHaveCount(10);
  await page.getByTestId("graph-node").filter({ hasText: "SCADA" }).click();
  const selection = page.getByTestId("graph-selection");
  await expect(selection).toContainText("IF-MES-004");
  await expect(selection).toContainText("IF-SCADA-001");
  await page.getByLabel("연동 방식").selectOption({ label: "MQ" });
  await expect(page.getByTestId("graph-edge")).toHaveCount(1);

  await page.getByRole("tab", { name: "대시보드" }).click();
  await expect(page.getByTestId("interface-total")).toHaveText("13");

  await page.getByRole("tab", { name: "목록" }).click();
  await expect(
    page.getByTestId("interface-table").locator("tbody tr"),
  ).toHaveCount(13);
  await page
    .getByRole("row", { name: /IF-WMS-004/ })
    .getByRole("button", { name: "수정" })
    .click();
  const form = page.getByTestId("interface-form");
  await form.getByLabel("상태").selectOption({ label: "운영" });
  await form.getByRole("button", { name: "저장" }).click();
  await expect(page.getByRole("row", { name: /IF-WMS-004/ })).toContainText(
    "운영",
  );

  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "엑셀 내보내기" }).click();
  expect((await download).suggestedFilename()).toBe("interfaces.xlsx");
});
