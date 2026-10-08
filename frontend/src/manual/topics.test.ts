import { TOPICS, isTopic, manualSource, manualTitle, topicForPath } from "./topics";

describe("manual topics", () => {
  it.each(TOPICS)("%s has a titled Korean and English page", (topic) => {
    for (const locale of ["ko", "en"] as const) expect(manualTitle(manualSource(locale, topic))).not.toBe("");
  });

  it("links only to existing topics", () => {
    for (const topic of TOPICS)
      for (const locale of ["ko", "en"] as const)
        for (const [, target] of manualSource(locale, topic).matchAll(/\]\(\/manual\/([^)#]+)\)/g))
          expect(isTopic(target)).toBe(true);
  });

  it("maps app routes to their topic", () => {
    expect(topicForPath("/flowdesk")).toBe("flowdesk");
    expect(topicForPath("/devtracker/projects/1")).toBe("devtracker");
    expect(topicForPath("/systems")).toBe("workspace");
    expect(topicForPath("/admin/users")).toBe("admin");
    expect(topicForPath("/")).toBe("start");
    expect(topicForPath("/flowdesker")).toBe("start");
  });
});
