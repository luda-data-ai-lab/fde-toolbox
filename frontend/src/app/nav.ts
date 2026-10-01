import type { Role } from "../api/types";
import { AUDIT_ROLES } from "./hooks";

export interface NavGroup {
  key: string;
  links: [to: string, labelKey: string][];
}

/** Sidebar groups by engagement stage (diagnose → operate) plus common; empty groups are omitted. */
export function navGroups(role: Role | undefined): NavGroup[] {
  const common: [string, string][] = [
    ["/engagements", "nav.engagements"],
    ["/systems", "nav.systems"],
    ["/files", "nav.files"],
    ["/assets", "nav.assets"],
  ];
  if (role && AUDIT_ROLES.includes(role)) common.push(["/audit", "nav.audit"]);
  if (role === "luda_admin") common.push(["/admin/tenants", "nav.tenants"], ["/admin/users", "nav.users"]);
  const groups: NavGroup[] = [
    { key: "home", links: [["/", "nav.home"]] },
    { key: "diagnose", links: [["/coachq", "nav.coachq"]] },
    { key: "analyze", links: [["/interfaces", "nav.interfaces"], ["/ontomap", "nav.ontomap"]] },
    { key: "design", links: [] },
    { key: "build", links: [["/devtracker", "nav.devtracker"]] },
    { key: "operate", links: [["/agenthub", "nav.agenthub"]] },
    { key: "common", links: common },
  ];
  return groups.filter((g) => g.links.length > 0);
}

/** Detail routes that belong to a tenant; switching tenant returns to their list page. */
export function tenantListPath(pathname: string): string | null {
  const m = /^\/devtracker\/projects\/[^/]+/.exec(pathname);
  return m ? "/devtracker" : null;
}
