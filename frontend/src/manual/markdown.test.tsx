import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Markdown } from "./markdown";
import { parseMarkdown } from "./parse";

describe("parseMarkdown", () => {
  it("parses headings, lists, tables, notes and code", () => {
    const blocks = parseMarkdown(
      "# Title\n\nIntro line\ncontinues\n\n- a\n- b\n\n1. one\n2. two\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\n> note\n\n```\nx = 1\n```\n",
    );
    expect(blocks.map((b) => b.kind)).toEqual(["heading", "paragraph", "list", "list", "table", "note", "code"]);
    expect(blocks[1]).toEqual({ kind: "paragraph", text: "Intro line continues" });
    expect(blocks[4]).toEqual({ kind: "table", header: ["A", "B"], rows: [["1", "2"]] });
    expect(blocks[6]).toEqual({ kind: "code", text: "x = 1" });
  });
});

describe("Markdown", () => {
  it("renders inline markup and only in-app links as links", () => {
    render(
      <MemoryRouter>
        <Markdown source={"Use **Save** and `npm ci`. See [FlowDesk](/manual/flowdesk) or [site](https://example.com)."} />
      </MemoryRouter>,
    );
    expect(screen.getByText("Save").tagName).toBe("STRONG");
    expect(screen.getByText("npm ci").tagName).toBe("CODE");
    expect(screen.getByRole("link", { name: "FlowDesk" })).toHaveAttribute("href", "/manual/flowdesk");
    expect(screen.queryByRole("link", { name: "site" })).toBeNull();
  });
});
