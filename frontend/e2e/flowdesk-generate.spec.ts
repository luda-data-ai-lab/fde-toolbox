import { expect, test } from "@playwright/test";

const RUN = `G${Date.now().toString(36).toUpperCase()}`;
const PASSWORD = "e2e-user-pass-123";

const ANSWER = {
  lanes: ["영업", "생산"],
  nodes: [
    { id: "n1", type: "start", label: "주문 시작", lane: "영업" },
    { id: "n2", type: "task", label: "주문 접수", lane: "영업", system: "mes" },
    { id: "n3", type: "decision", label: "재고 있음?", lane: "생산" },
    { id: "n4", type: "end", label: "출하 완료", lane: "생산" },
  ],
  edges: [
    { source: "n1", target: "n2" },
    { source: "n2", target: "n3" },
    { source: "n3", target: "n4", label: "예" },
  ],
};

test("FDE builds a perspective prompt from insights and creates a flow from a pasted answer", async ({
  page,
  request,
}) => {
  await request.post("/api/v1/auth/login", { data: { email: "admin@e2e.local", password: "admin-pass-123" } });
  const tenant = (await (
    await request.post("/api/v1/admin/tenants", { data: { name: `FG-${RUN}`, code: RUN } })
  ).json()) as { id: string };
  await request.post("/api/v1/admin/users", {
    data: { email: `fde-${RUN}@e2e.local`, name: "FDE", role: "fde", password: PASSWORD, tenant_ids: [tenant.id] },
  });
  const base = `/api/v1/t/${tenant.id}`;
  const eng = (await (await request.post(`${base}/engagements`, { data: { name: "흐름 생성" } })).json()) as {
    id: string;
  };
  const mes = (await (
    await request.post(`${base}/systems`, { data: { name: "생산관리 MES", short_name: "MES", type: "MES" } })
  ).json()) as { id: string };
  const session = (await (
    await request.post(`${base}/discoveryq/sessions`, { data: { engagement_id: eng.id, title: "영업 인터뷰" } })
  ).json()) as { id: string };
  await request.post(`${base}/discoveryq/sessions/${session.id}/insights`, {
    data: { text: "주문은 메일로 받아 엑셀에 다시 입력한다" },
  });

  await page.goto("/login");
  await page.getByLabel("이메일").fill(`fde-${RUN}@e2e.local`);
  await page.getByLabel("비밀번호").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await page.getByRole("link", { name: "FlowDesk" }).click();
  await page.getByLabel("프로젝트(인게이지먼트)").selectOption(eng.id);

  const gen = page.getByRole("region", { name: "흐름 생성(프롬프트·LLM)" });
  await gen.getByLabel("제목").fill("주문 처리 생성");
  await gen.getByLabel("관점").selectOption("developer");
  await gen
    .getByTestId("gen-insights")
    .getByLabel(/엑셀에 다시 입력/)
    .check();
  await gen.getByRole("button", { name: "프롬프트 만들기" }).click();

  const prompt = gen.getByRole("textbox", { name: "프롬프트", exact: true });
  await expect(prompt).toHaveValue(/Developer:/);
  await expect(prompt).toHaveValue(/엑셀에 다시 입력/);
  await expect(prompt).toHaveValue(/생산관리 MES \(MES\)/);
  await expect(gen.getByRole("button", { name: "LLM으로 자동 생성" })).toHaveCount(0);

  await gen.getByRole("textbox", { name: "LLM 결과 붙여넣기" }).fill("설명 없이 JSON이 아님");
  await gen.getByRole("button", { name: "결과로 흐름 만들기" }).click();
  await expect(gen.getByRole("alert")).toContainText("LLM 결과를 흐름으로 바꾸지 못했습니다");

  await gen.getByRole("textbox", { name: "LLM 결과 붙여넣기" }).fill("```json\n" + JSON.stringify(ANSWER) + "\n```");
  await gen.getByRole("button", { name: "결과로 흐름 만들기" }).click();

  const nodes = page.getByTestId("flow-node");
  await expect(nodes).toHaveCount(4);
  await expect(page.getByLabel("제목")).toHaveValue("주문 처리 생성");
  await nodes.filter({ hasText: "주문 접수" }).click();
  await expect(
    page
      .getByTestId("node-panel")
      .locator("label", { hasText: /^시스템/ })
      .locator("select"),
  ).toHaveValue(mes.id);
});
