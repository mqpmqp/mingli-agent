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

test("loads the repository wheel in Pyodide and matches CPython 3.11", async ({ page }) => {
  const expected = JSON.parse(
    execFileSync(PYTHON, ["-X", "utf8", "-c", PYTHON_REFERENCE, JSON.stringify(INPUT)], {
      cwd: REPO_ROOT,
      encoding: "utf8",
    }),
  );

  await page.goto("/tests/fixtures/poc.html");
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
