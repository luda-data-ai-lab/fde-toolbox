import { expect, test } from "@playwright/test";

test("manual opens the page for the current screen and follows the UI language", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("이메일").fill("admin@e2e.local");
  await page.getByLabel("비밀번호").fill("admin-pass-123");
  await page.getByRole("button", { name: "로그인" }).click();
  await page.getByRole("link", { name: "FlowDesk" }).click();
  await page.getByRole("link", { name: "매뉴얼" }).click();
  await expect(page).toHaveURL(/\/manual\/flowdesk$/);
  const content = page.getByTestId("manual-content");
  await expect(content.getByRole("heading", { level: 1, name: "FlowDesk" })).toBeVisible();
  await expect(content.getByRole("heading", { name: "스냅샷" })).toBeVisible();

  const contents = page.getByRole("navigation", { name: "목차" });
  await contents.getByRole("link", { name: "I/F 관리" }).click();
  await expect(content.getByRole("heading", { level: 1, name: "I/F 관리" })).toBeVisible();

  await page.getByRole("button", { name: "English" }).click();
  await expect(content.getByRole("heading", { level: 1, name: "I/F management" })).toBeVisible();
  await page.getByRole("navigation", { name: "Contents" }).getByRole("link", { name: "Getting started" }).click();
  await content.getByRole("link", { name: "DiscoveryQ" }).click();
  await expect(page).toHaveURL(/\/manual\/discoveryq$/);
});
