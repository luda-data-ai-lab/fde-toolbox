import { expect, test } from "@playwright/test";

const RUN = `M${Date.now().toString(36).toUpperCase()}`;
const PASSWORD = "e2e-user-pass-123";

test("FDE maps concepts to systems, columns and I/Fs and reviews coverage", async ({
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
  const post = async (path: string, data: object) => {
    const res = await request.post(`${base}${path}`, { data });
    expect(res.status()).toBe(201);
    return (await res.json()) as { id: string };
  };
  const erp = await post("/systems", { name: "ERP", type: "ERP" });
  const mes = await post("/systems", { name: "MES", type: "MES" });
  await post("/interfaces", {
    if_code: "IF-LOT-01",
    name: "로트 실적",
    source_system_id: mes.id,
    target_system_id: erp.id,
  });
  const lot = await post("/ontomap/concepts", {
    name: "생산 로트",
    definition: "배합 단위",
    status: "confirmed",
  });
  const product = await post("/ontomap/concepts", { name: "제품" });
  await post(`/ontomap/concepts/${lot.id}/attributes`, { name: "로트번호" });
  await post(`/ontomap/concepts/${lot.id}/attributes`, { name: "점도" });
  await post("/ontomap/relations", {
    source_concept_id: lot.id,
    name: "produces",
    target_concept_id: product.id,
  });

  await page.goto("/login");
  await page.getByLabel("이메일").fill(`fde-${RUN}@e2e.local`);
  await page.getByLabel("비밀번호").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await page.getByRole("link", { name: "OntoMap 용어 사전" }).click();

  await page.getByRole("tab", { name: "검증" }).click();
  await expect(
    page
      .getByTestId("validation-row")
      .filter({ hasText: "확정된 개념에 데이터 매핑이 없습니다." }),
  ).toContainText("생산 로트");

  await page.getByRole("tab", { name: "개념 모델" }).click();
  await page
    .getByTestId("concept-row")
    .filter({ hasText: "생산 로트" })
    .click();
  const detail = page.getByTestId("concept-detail");
  const form = detail.getByRole("form", { name: "매핑 추가" });

  await form
    .getByRole("combobox", { name: "시스템", exact: true })
    .selectOption({ label: "MES" });
  await form
    .getByRole("combobox", { name: "테이블", exact: true })
    .fill("mes_lot");
  await form.getByRole("button", { name: "매핑 추가" }).click();
  await expect(detail.getByTestId("mapping-row")).toHaveCount(1);

  await form
    .getByRole("combobox", { name: "매핑 대상", exact: true })
    .selectOption({ label: "속성: 로트번호" });
  await form.getByRole("button", { name: "매핑 추가" }).click();
  await expect(form.getByText("매핑 위치가 부족합니다")).toBeVisible();
  await form
    .getByRole("combobox", { name: "테이블", exact: true })
    .fill("mes_lot");
  await form
    .getByRole("combobox", { name: "컬럼", exact: true })
    .fill("lot_no");
  await form.getByRole("button", { name: "매핑 추가" }).click();
  await expect(detail.getByTestId("mapping-row")).toHaveCount(2);

  await form
    .getByRole("combobox", { name: "매핑 대상", exact: true })
    .selectOption({ label: "관계: produces" });
  await form
    .getByRole("combobox", { name: "I/F", exact: true })
    .selectOption({ label: "IF-LOT-01 로트 실적" });
  await expect(
    form.getByRole("combobox", { name: "매핑 출처", exact: true }),
  ).toHaveValue("interface");
  await form.getByRole("button", { name: "매핑 추가" }).click();
  const rows = detail.getByTestId("mapping-row");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(1)).toContainText("mes_lot.lot_no");
  await expect(rows.nth(2)).toContainText("IF-LOT-01");

  await page.getByRole("tab", { name: "매핑 커버리지" }).click();
  const row = page.getByTestId("coverage-row").filter({ hasText: "생산 로트" });
  await expect(row).toContainText("MES");
  await expect(row).toContainText("1 / 2");
  await expect(row).toContainText("점도");

  await page.getByRole("tab", { name: "검증" }).click();
  await expect(
    page
      .getByTestId("validation-row")
      .filter({ hasText: "확정된 개념에 데이터 매핑이 없습니다." }),
  ).toHaveCount(0);
});
