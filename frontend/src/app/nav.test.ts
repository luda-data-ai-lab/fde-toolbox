import { describe, expect, it } from "vitest";
import { navGroups, tenantListPath } from "./nav";

const paths = (role: Parameters<typeof navGroups>[0]) => navGroups(role).flatMap((g) => g.links.map(([to]) => to));

describe("navGroups", () => {
  it("orders stage groups and hides empty ones", () => {
    expect(navGroups("fde").map((g) => g.key)).toEqual(["home", "analyze", "build", "operate", "common"]);
  });

  it("shows admin screens only to luda_admin and audit to audit roles", () => {
    expect(paths("luda_admin")).toEqual(expect.arrayContaining(["/admin/tenants", "/admin/users", "/audit"]));
    expect(paths("fde")).not.toContain("/admin/users");
    expect(paths("client_admin")).toContain("/audit");
    expect(paths("client_user")).not.toContain("/audit");
  });
});

describe("tenantListPath", () => {
  it("maps tenant detail routes to their list", () => {
    expect(tenantListPath("/devtracker/projects/abc")).toBe("/devtracker");
    expect(tenantListPath("/systems")).toBeNull();
    expect(tenantListPath("/agenthub/templates/x")).toBeNull();
  });
});
