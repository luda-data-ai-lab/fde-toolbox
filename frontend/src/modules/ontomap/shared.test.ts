import { describe, expect, it } from "vitest";
import { formatAliases, parseAliases } from "./shared";

describe("aliases text", () => {
  it("parses department-qualified aliases", () => {
    expect(parseAliases("생산팀: 배합표; 품질팀：레시피, BOM\n")).toEqual([
      { alias: "배합표", department: "생산팀" },
      { alias: "레시피", department: "품질팀" },
      { alias: "BOM", department: null },
    ]);
    expect(parseAliases(" ; : ")).toEqual([]);
  });

  it("round-trips through formatAliases", () => {
    const text = "생산팀: 배합표; BOM";
    expect(formatAliases(parseAliases(text))).toBe(text);
  });
});
