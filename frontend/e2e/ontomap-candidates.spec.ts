import { expect, test } from "@playwright/test";

const RUN = `C${Date.now().toString(36).toUpperCase()}`;
const PASSWORD = "e2e-user-pass-123";

test("FDE extracts OntoMap candidates from I/Fs and FlowDesk, confirms and merges them, and uses LLM copy mode", async ({
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
  const base = `/api/v1/t/${tenant.id}`;
  const post = async (path: string, data: object) => {
    const res = await request.post(`${base}${path}`, { data });
    expect(res.status()).toBe(201);
    return (await res.json()) as { id: string };
  };
  const erp = await post("/systems", { name: "ERP", type: "ERP" });
  const mes = await post("/systems", { name: "MES", type: "MES" });
  await post("/interfaces", {
    if_code: "IF-ORD-01",
    name: "수주 정보 전송",
    description: "고객 수주 헤더",
    source_system_id: erp.id,
    target_system_id: mes.id,
  });
  const engagement = await post("/engagements", { name: "E2E 과제" });
  await post("/flowdesk/flows", {
    engagement_id: engagement.id,
    title: "출하",
    graph: {
      lanes: ["물류"],
      nodes: [
        { id: "d", type: "document", label: "출하 지시서", lane: "물류" },
      ],
    },
  });
  await post("/ontomap/concepts", { name: "출하지시서" });

  await page.goto("/login");
  await page.getByLabel("이메일").fill(`fde-${RUN}@e2e.local`);
  await page.getByLabel("비밀번호").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await page.getByRole("link", { name: "OntoMap 용어 사전" }).click();
  await page.getByRole("tab", { name: "후보" }).click();

  const extract = page.getByRole("region", { name: "후보 추출" });
  await extract.getByRole("button", { name: "I/F에서 추출" }).click();
  await expect(extract.getByRole("status")).toContainText("새 후보 1건");
  await extract.getByRole("button", { name: "I/F에서 추출" }).click();
  await expect(extract.getByRole("status")).toContainText(
    "새 후보 0건, 이미 있는 후보 1건",
  );
  await extract.getByRole("button", { name: "FlowDesk에서 추출" }).click();
  await expect(extract.getByRole("status")).toContainText("새 후보 1건");

  const rows = page.getByTestId("candidate-row");
  await expect(rows).toHaveCount(2);
  const order = rows.filter({ hasText: "수주" });
  await expect(order).toContainText("IF-ORD-01");
  await expect(order).toContainText("고객 수주 헤더");
  await order.getByRole("button", { name: "확정" }).click();
  await expect(rows).toHaveCount(1);

  const doc = rows.filter({ hasText: "출하 지시서" });
  await expect(doc).toContainText("물류");
  await expect(doc.getByTestId("similar")).toContainText("출하지시서");
  await doc.getByRole("button", { name: "출하지시서에 병합" }).click();
  await expect(rows).toHaveCount(0);

  const suggest = page.getByRole("region", { name: "LLM 제안" });
  await suggest.getByLabel("제안 종류").selectOption("relations");
  await suggest.getByRole("button", { name: "프롬프트 만들기" }).click();
  await expect(
    suggest.getByRole("textbox", { name: "프롬프트", exact: true }),
  ).toHaveValue(/출하지시서/);
  await expect(
    suggest.getByRole("button", { name: "LLM으로 제안 받기" }),
  ).toHaveCount(0);
  await suggest.getByLabel("LLM 응답(JSON)").fill(
    JSON.stringify({
      relations: [
        {
          source: "수주",
          name: "근거가 된다",
          target: "출하지시서",
          cardinality: "1:N",
        },
      ],
    }),
  );
  await suggest.getByRole("button", { name: "응답으로 후보 만들기" }).click();
  await expect(suggest.getByRole("status")).toContainText("새 후보 1건");
  const rel = rows.filter({ hasText: "수주 —근거가 된다→ 출하지시서" });
  await expect(rel).toContainText("LLM 제안");
  await rel.getByRole("button", { name: "확정" }).click();
  await expect(rows).toHaveCount(0);

  await page.getByRole("tab", { name: "개념 모델" }).click();
  await expect(page.getByRole("row", { name: "수주 확정" })).toBeVisible();
});
