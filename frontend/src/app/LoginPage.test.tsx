import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { LoginPage } from "./LoginPage";

afterEach(() => vi.restoreAllMocks());

describe("LoginPage", () => {
  it("shows a translated error on bad credentials", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "invalid_credentials" } }), {
        status: 401,
        headers: { "content-type": "application/json" },
      }),
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await userEvent.type(screen.getByLabelText("이메일"), "a@b.co");
    await userEvent.type(screen.getByLabelText("비밀번호"), "wrong-pass");
    await userEvent.click(screen.getByRole("button", { name: "로그인" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("이메일 또는 비밀번호가 올바르지 않습니다.");
  });
});
