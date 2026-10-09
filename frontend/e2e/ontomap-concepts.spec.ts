import { expect, test } from "@playwright/test";

const RUN = `C${Date.now().toString(36).toUpperCase()}`;
const PASSWORD = "e2e-user-pass-123";

test("FDE builds a concept model on top of the upper ontology", async ({
  page,
  request,
}) => {
  await request.post("/api/v1/auth/login", {
    data: { email: "admin@e2e.local", password: "admin-pass-123" },
  });
  const tenant = (await (
    await request.post("/api/v1/admin/tenants", {
      data: { name: `OC-${RUN}`, code: RUN },
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

  await page.goto("/login");
  await page.getByLabel("이메일").fill(`fde-${RUN}@e2e.local`);
  await page.getByLabel("비밀번호").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await page.getByRole("link", { name: "OntoMap 용어 사전" }).click();
  await page.getByRole("tab", { name: "개념 모델" }).click();

  const form = page.getByRole("form", { name: "개념 등록" });
  await form.getByLabel("개념 이름").fill("생산 로트");
  await form
    .getByRole("combobox", { name: "상위 개념" })
    .selectOption({ label: "로트 (lot)" });
  await form.getByRole("button", { name: "개념 등록" }).click();
  const detail = page.getByTestId("concept-detail");
  await expect(detail.getByTestId("concept-ancestors")).toContainText(
    "생산 로트 → 로트",
  );
  await expect(detail.getByTestId("inherited-row").first()).toBeVisible();

  const attrForm = detail.getByRole("form", { name: "속성 추가" });
  await attrForm.getByLabel("속성 이름").fill("LOT 번호");
  await attrForm.getByRole("button", { name: "속성 추가" }).click();
  await expect(detail.getByTestId("attribute-row")).toContainText("LOT 번호");
  await detail.getByRole("button", { name: "식별자로 지정" }).click();
  await expect(detail.getByTestId("attribute-row")).toContainText("식별자");

  await form.getByLabel("개념 이름").fill("반제품 로트");
  await form
    .getByRole("combobox", { name: "상위 개념" })
    .selectOption({ label: "생산 로트" });
  await form.getByRole("button", { name: "개념 등록" }).click();
  await expect(detail.getByTestId("concept-ancestors")).toContainText(
    "반제품 로트 → 생산 로트 → 로트",
  );
  await expect(detail).toContainText("상속: 생산 로트");

  const relForm = detail.getByRole("form", { name: "관계 추가" });
  await relForm.getByLabel("관계 이름", { exact: true }).fill("투입된다");
  await relForm
    .getByRole("combobox", { name: "대상 개념" })
    .selectOption({ label: "생산 로트" });
  await relForm.getByRole("button", { name: "관계 추가" }).click();
  await expect(detail.getByTestId("relation-row")).toContainText("투입된다");

  await page
    .getByTestId("concept-row")
    .filter({ hasText: "생산 로트", hasNotText: "반제품" })
    .click();
  await detail
    .getByRole("combobox", { name: "상위 개념 변경" })
    .selectOption({ label: "반제품 로트" });
  await expect(detail.getByRole("alert")).toContainText("순환 상속");

  await page.getByRole("tab", { name: "검증" }).click();
  await expect(page.getByTestId("validation-table")).toHaveCount(0);
});
