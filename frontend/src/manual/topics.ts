export const TOPICS = [
  "start",
  "discoveryq",
  "interfaces",
  "ontomap",
  "flowdesk",
  "devtracker",
  "agenthub",
  "workspace",
  "adapters",
  "admin",
  "setup",
] as const;
export type Topic = (typeof TOPICS)[number];
export type ManualLocale = "ko" | "en";

const files = import.meta.glob<string>("./*/*.md", { query: "?raw", import: "default", eager: true });

export function manualSource(locale: ManualLocale, topic: Topic): string {
  return files[`./${locale}/${topic}.md`] ?? "";
}

export function manualTitle(source: string): string {
  return /^#\s+(.+)$/m.exec(source)?.[1]?.trim() ?? "";
}

export function isTopic(value: string | undefined): value is Topic {
  return TOPICS.some((t) => t === value);
}

const ROUTE_TOPICS: [prefix: string, topic: Topic][] = [
  ["/discoveryq", "discoveryq"],
  ["/interfaces", "interfaces"],
  ["/ontomap", "ontomap"],
  ["/flowdesk", "flowdesk"],
  ["/devtracker", "devtracker"],
  ["/agenthub", "agenthub"],
  ["/engagements", "workspace"],
  ["/systems", "workspace"],
  ["/files", "workspace"],
  ["/assets", "workspace"],
  ["/audit", "workspace"],
  ["/adapters", "adapters"],
  ["/admin", "admin"],
];

/** Manual topic that explains the screen at `pathname` (the getting-started page otherwise). */
export function topicForPath(pathname: string): Topic {
  return ROUTE_TOPICS.find(([p]) => pathname === p || pathname.startsWith(`${p}/`))?.[1] ?? "start";
}
