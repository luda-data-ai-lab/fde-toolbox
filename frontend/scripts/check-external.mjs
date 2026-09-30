// Fails when the build output references any remote resource (CDN, fonts, analytics).
import { readdirSync, readFileSync, statSync } from "node:fs";
import { extname, join } from "node:path";

const root = process.argv[2] ?? "dist";
const PATTERN =
  /(?:<(?:script|link|img|source|iframe)[^>]+(?:src|href)\s*=\s*["']?|url\(\s*["']?|@import\s+["']|import\(\s*["'])(https?:)?\/\//gi;
const EXT = new Set([".html", ".css", ".js", ".svg", ".webmanifest"]);

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* walk(p);
    else if (EXT.has(extname(p))) yield p;
  }
}

const hits = [];
for (const file of walk(root)) {
  const text = readFileSync(file, "utf8");
  for (const m of text.matchAll(PATTERN)) hits.push(`${file}: ${text.slice(m.index, m.index + 100)}`);
}
if (hits.length) {
  console.error(`external resource references found:\n${hits.join("\n")}`);
  process.exit(1);
}
console.log(`no external resource references in ${root}`);
