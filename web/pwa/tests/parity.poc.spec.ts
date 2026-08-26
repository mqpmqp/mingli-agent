import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "../../..");
const PYTHON = process.env.PWA_PYTHON ?? "python";
const INPUT = {
  gender: "male",
  calendar: "solar",
  birth_date: "2000-01-07",
  birth_time: "12:00",
  timezone: "Asia/Shanghai",
  longitude: 121.4737,
  latitude: 31.2304,
  true_solar_time: false,
};

const PYTHON_REFERENCE = String.raw`
import json, sys
from mingli.bazi import DeterministicBaziEngine

result = DeterministicBaziEngine().calculate(json.loads(sys.argv[1]))
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
`;

declare global {
  interface Window {
    __mingliPwa?: {
      ready: Promise<void>;
      calculate(input: Record<string, unknown>): Promise<Record<string, unknown>>;
      versions(): Promise<Record<string, string>>;
    };
  }
}

const PYODIDE_BOOTSTRAP_ASSETS = [
  "pyodide/pyodide.asm.js",
  "pyodide/pyodide.asm.wasm",
  "pyodide/python_stdlib.zip",
  "pyodide/pyodide-lock.json",
] as const;

for (const asset of PYODIDE_BOOTSTRAP_ASSETS) {
  test("rejects tampered " + asset + " before Pyodide executes it", async ({ page }) => {
    test.setTimeout(120_000);
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "serviceWorker", {
        configurable: true,
        value: {
          register: async () => {
            throw new Error("service worker disabled for runtime-integrity isolation");
          },
        },
      });
    });
    await page.route("**/runtime/" + asset, async (route) => {
      const upstream = await route.fetch();
      const tampered = Buffer.from(await upstream.body());
      tampered[0] = tampered[0] === 0 ? 1 : 0;
      await route.fulfill({ response: upstream, body: tampered });
    });

    await page.goto("/");
    const status = page.getByTestId("runtime-status");
    await expect(status).toHaveAttribute("data-state", "error", { timeout: 120_000 });
    await expect(status).toContainText("SHA256 校验失败：" + asset);
  });
}

test("loads the repository wheel in Pyodide and matches CPython 3.11", async ({ page }) => {
  const expected = JSON.parse(
    execFileSync(PYTHON, ["-X", "utf8", "-c", PYTHON_REFERENCE, JSON.stringify(INPUT)], {
      cwd: REPO_ROOT,
      encoding: "utf8",
    }),
  );

  await page.goto("/");
  await page.waitForFunction(() => Boolean(window.__mingliPwa), undefined, { timeout: 15_000 });
  const actual = await page.evaluate(async (input) => {
    if (!window.__mingliPwa) throw new Error("MingLi Pyodide runtime is unavailable");
    await window.__mingliPwa.ready;
    return window.__mingliPwa.calculate(input);
  }, INPUT);

  expect(actual).toEqual(expected);
  const versions = await page.evaluate(() => window.__mingliPwa!.versions());
  expect(versions.pyodide).toBe("0.25.1");
  expect(versions.python).toMatch(/^3\.11\./);
  expect(versions.tzdata).toBe("2025.2");
});
