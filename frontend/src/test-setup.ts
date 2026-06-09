import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { afterEach, vi } from "vitest";

const PUBLIC_DIR = resolve(__dirname, "../public");

/**
 * Stub global `fetch` so vendored code (and our loaders) can resolve paths
 * starting with `/` against the public/ directory in tests.
 */
function stubFetch(): void {
  vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url.startsWith("/")) {
      try {
        const body = readFileSync(resolve(PUBLIC_DIR, "." + url), "utf8");
        return new Response(body, {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      } catch {
        return new Response("not found", { status: 404 });
      }
    }
    return new Response("not found", { status: 404 });
  });
}

stubFetch();

afterEach(() => {
  vi.restoreAllMocks();
  stubFetch();
});
