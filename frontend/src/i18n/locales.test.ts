import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import en from "./locales/en.json";
import ko from "./locales/ko.json";

function keys(obj: object, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === "object" ? keys(v as object, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = join(dir, e.name);
    if (e.isDirectory()) return sources(p);
    return /\.tsx?$/.test(e.name) && !e.name.includes(".test.") ? [p] : [];
  });
}

describe("locales", () => {
  it("ko and en have identical keys", () => {
    expect(keys(en).sort()).toEqual(keys(ko).sort());
  });

  it("every static t() key used in source exists", () => {
    const known = new Set(keys(ko));
    const missing = new Set<string>();
    for (const file of sources(join(process.cwd(), "src"))) {
      for (const m of readFileSync(file, "utf8").matchAll(/\bt\("([a-zA-Z_]+\.[a-zA-Z_.]+)"/g)) {
        const key = m[1] ?? "";
        if (!known.has(key)) missing.add(`${file}: ${key}`);
      }
    }
    expect([...missing]).toEqual([]);
  });
});
