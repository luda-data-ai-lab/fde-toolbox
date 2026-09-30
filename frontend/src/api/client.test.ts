import { ApiError, api } from "./client";

afterEach(() => vi.restoreAllMocks());

function mockFetch(status: number, body: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

describe("api client", () => {
  it("sends same-origin JSON requests with query params", async () => {
    const f = mockFetch(200, { ok: true });
    await api("/t/x/systems", { method: "POST", body: { a: 1 }, query: { limit: 5, empty: "", ids: ["1", "2"] } });
    const [url, init] = f.mock.calls[0] ?? [];
    expect(url).toBe("/api/v1/t/x/systems?limit=5&ids=1&ids=2");
    expect(init?.credentials).toBe("same-origin");
    expect(init?.body).toBe('{"a":1}');
  });

  it("maps the error envelope to ApiError", async () => {
    mockFetch(404, { error: { code: "not_found", message: "errors.not_found" } });
    await expect(api("/x")).rejects.toMatchObject({ status: 404, code: "not_found" });
  });

  it("handles 204", async () => {
    mockFetch(204, undefined);
    await expect(api("/x", { method: "DELETE" })).resolves.toBeUndefined();
    expect(new ApiError(500, "x")).toBeInstanceOf(Error);
  });
});
