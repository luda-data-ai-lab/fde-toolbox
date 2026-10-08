import { describe, expect, it } from "vitest";
import type { FlowGraph } from "../../api/types";
import { LANE_HEIGHT, graphToSvg, laneAt, nextId } from "./shared";

const graph: FlowGraph = {
  schema_version: 1,
  lanes: ["영업", "생산"],
  nodes: [
    { id: "a", type: "start", label: "시작 <A>", lane: "영업", position: { x: 0, y: 40 } },
    { id: "b", type: "system", label: "", lane: "생산", system_id: "s1", position: { x: 220, y: 180 } },
  ],
  edges: [{ id: "e1", source: "a", target: "b", label: "예" }],
};

describe("flowdesk helpers", () => {
  it("maps y to lanes", () => {
    expect(laneAt(["A", "B"], 10)).toBe("A");
    expect(laneAt(["A", "B"], LANE_HEIGHT + 10)).toBe("B");
    expect(laneAt(["A", "B"], LANE_HEIGHT * 5)).toBeNull();
    expect(laneAt([], 0)).toBeNull();
  });

  it("generates unused ids", () => {
    expect(nextId("n", ["n1", "n3"])).toBe("n4");
    expect(nextId("n", ["n3"])).toBe("n2");
  });

  it("renders a standalone, escaped SVG with lanes, system names and edge labels", () => {
    const { svg, width, height } = graphToSvg(graph, new Map([["s1", "MES"]]));
    expect(svg.startsWith("<svg")).toBe(true);
    expect(svg).toContain("시작 &lt;A&gt;");
    expect(svg).toContain(">MES<");
    expect(svg).toContain(">영업<");
    expect(svg).toContain(">예<");
    expect(svg).not.toMatch(/https?:\/\/(?!www\.w3\.org)/);
    expect(width).toBeGreaterThan(220);
    expect(height).toBeGreaterThanOrEqual(2 * LANE_HEIGHT);
  });
});
