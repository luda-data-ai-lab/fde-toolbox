import { describe, expect, it } from "vitest";
import type { GraphEdge, GraphNode } from "../../api/types";
import { circleLayout, groupEdges, linkPath } from "./graphLayout";

const node = (id: string, degree: number): GraphNode => ({
  id,
  name: id,
  short_name: null,
  type: "OTHER",
  degree,
});
const edge = (id: string, source: string, target: string): GraphEdge => ({
  id,
  source,
  target,
  if_code: id,
  name: id,
  link_type: "api",
  status: "operating",
});

describe("circleLayout", () => {
  it("puts the busiest node on top and keeps all nodes inside the canvas", () => {
    const pos = circleLayout(
      [node("a", 1), node("hub", 9), node("c", 0)],
      400,
      300,
    );
    expect(pos.get("hub")).toEqual({ x: 200, y: 70 });
    for (const p of pos.values()) {
      expect(p.x).toBeGreaterThanOrEqual(0);
      expect(p.y).toBeLessThanOrEqual(300);
    }
  });
});

describe("groupEdges", () => {
  it("groups interfaces per directed system pair", () => {
    const groups = groupEdges([
      edge("1", "a", "b"),
      edge("2", "a", "b"),
      edge("3", "b", "a"),
    ]);
    expect(groups.map((g) => [g.key, g.edges.length])).toEqual([
      ["a->b", 2],
      ["b->a", 1],
    ]);
  });
});

describe("linkPath", () => {
  it("draws a loop for self links and a curve otherwise", () => {
    expect(linkPath({ x: 10, y: 10 }, { x: 10, y: 10 })).toContain("C");
    expect(linkPath({ x: 0, y: 0 }, { x: 100, y: 0 })).toMatch(/^M 22 0 Q/);
  });
});
