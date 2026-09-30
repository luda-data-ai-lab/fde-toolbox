import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { Role } from "../api/types";
import { RequireRole } from "./App";

function renderAs(role: Role) {
  const qc = new QueryClient();
  qc.setQueryData(["me"], { user: { id: "u", email: "u@x.co", name: "U", role }, tenants: [] });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <RequireRole roles={["luda_admin", "client_admin"]}>
          <p>secret page</p>
        </RequireRole>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RequireRole", () => {
  it("renders children for allowed roles", () => {
    renderAs("client_admin");
    expect(screen.getByText("secret page")).toBeInTheDocument();
  });

  it("shows forbidden instead of the page for other roles", () => {
    renderAs("client_user");
    expect(screen.queryByText("secret page")).not.toBeInTheDocument();
    expect(screen.getByText("권한이 없습니다.")).toBeInTheDocument();
  });
});
