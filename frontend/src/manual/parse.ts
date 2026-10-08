export type Block =
  | { kind: "heading"; level: 1 | 2 | 3; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; ordered: boolean; items: string[] }
  | { kind: "code"; text: string }
  | { kind: "note"; text: string }
  | { kind: "table"; header: string[]; rows: string[][] };

const cells = (line: string) =>
  line
    .trim()
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((c) => c.trim());

/** Parses the small Markdown subset used by the manual (headings, lists, tables, code, notes). */
export function parseMarkdown(source: string): Block[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;
  const at = (n: number) => lines[n] ?? "";
  while (i < lines.length) {
    const line = at(i);
    if (!line.trim()) {
      i++;
      continue;
    }
    if (line.startsWith("```")) {
      const body: string[] = [];
      i++;
      while (i < lines.length && !at(i).startsWith("```")) body.push(at(i++));
      i++;
      blocks.push({ kind: "code", text: body.join("\n") });
      continue;
    }
    const h = /^(#{1,3})\s+(.*)$/.exec(line);
    if (h) {
      blocks.push({ kind: "heading", level: (h[1] ?? "#").length as 1 | 2 | 3, text: (h[2] ?? "").trim() });
      i++;
      continue;
    }
    if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && at(i).startsWith("|")) {
        const row = cells(at(i++));
        if (!row.every((c) => /^:?-{3,}:?$/.test(c))) rows.push(row);
      }
      blocks.push({ kind: "table", header: rows[0] ?? [], rows: rows.slice(1) });
      continue;
    }
    if (line.startsWith(">")) {
      const body: string[] = [];
      while (i < lines.length && at(i).startsWith(">")) body.push(at(i++).replace(/^>\s?/, ""));
      blocks.push({ kind: "note", text: body.join(" ") });
      continue;
    }
    const item = /^(-|\d+\.)\s+/;
    const m = item.exec(line);
    if (m) {
      const ordered = m[1] !== "-";
      const items: string[] = [];
      while (i < lines.length) {
        const cur = at(i);
        const im = item.exec(cur);
        if (im && im[1] !== "-" === ordered) items.push(cur.slice(im[0].length));
        else if (/^\s{2,}\S/.test(cur) && items.length) items[items.length - 1] += ` ${cur.trim()}`;
        else break;
        i++;
      }
      blocks.push({ kind: "list", ordered, items });
      continue;
    }
    const body: string[] = [];
    while (i < lines.length && at(i).trim() && !/^(#|```|\||>|-\s|\d+\.\s)/.test(at(i))) body.push(at(i++).trim());
    blocks.push({ kind: "paragraph", text: body.join(" ") });
  }
  return blocks;
}

export function slug(text: string): string {
  return text
    .toLowerCase()
    .replace(/[`*]/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-|-$/g, "");
}
