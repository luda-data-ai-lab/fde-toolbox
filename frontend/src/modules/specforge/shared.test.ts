import { describe, expect, it } from "vitest";
import { toggle } from "./shared";

describe("toggle", () => {
  it("adds and removes ids", () => {
    expect(toggle(["a"], "b")).toEqual(["a", "b"]);
    expect(toggle(["a", "b"], "a")).toEqual(["b"]);
  });
});
