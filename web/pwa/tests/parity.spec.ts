import { expect, test, type Page } from "@playwright/test";

type JsonRecord = Record<string, unknown>;

type SuccessfulOutcome = {
  ok: true;
  canonical_hash: string;
  result: JsonRecord & {
    pillars: JsonRecord;
    luck: JsonRecord;
  };
};

type ErrorOutcome = {
  ok: false;
  error: {
    code: string;
  };
};

type RuntimeOutcome = SuccessfulOutcome | ErrorOutcome;

type ParityCase = {
  id: string;
  category: string;
  expected_error: string | null;
  input: JsonRecord;
  outcome: RuntimeOutcome;
};

type DeterminismSample = {
  canonical_hash: string;
  pillars: JsonRecord;
  luck: JsonRecord;
};

type DeterminismSummary = {
  runs: number;
  samples: DeterminismSample[];
};

type RuntimeWindow = Window & {
  __mingliPwa?: {
    ready: Promise<void>;
    calculateOutcome(input: JsonRecord): Promise<RuntimeOutcome>;
    determinism(input: JsonRecord, runs: number): Promise<DeterminismSummary>;
    versions(): Promise<Record<string, string>>;
  };
};

async function openRuntime(page: Page): Promise<void> {
  await page.goto("/");
  await page.waitForFunction(() => Boolean((window as RuntimeWindow).__mingliPwa), undefined, { timeout: 15_000 });
}

test.describe("CPython reference to mobile Chromium parity", () => {
  test("uses the pinned browser runtime and verifies Asia/Shanghai ZoneInfo", async ({ page }) => {
    test.setTimeout(120_000);
    expect(page.viewportSize()).toEqual({ width: 390, height: 844 });
    await openRuntime(page);

    const versions = await page.evaluate(async () => {
      const runtime = (window as RuntimeWindow).__mingliPwa;
      if (!runtime) throw new Error("MingLi Pyodide runtime is unavailable");
      await runtime.ready;
      return runtime.versions();
    });

    expect(versions.pyodide).toBe("0.25.1");
    expect(versions.python).toMatch(/^3\.11\./);
    expect(versions.tzdata).toBe("2025.2");
    expect(versions.zoneInfoAsiaShanghai).toBe("verified");
  });

  test("matches every one of the 154 generated reference outcomes", async ({ page }) => {
    test.setTimeout(600_000);
    await openRuntime(page);

    const parity = await page.evaluate(async () => {
      const runtime = (window as RuntimeWindow).__mingliPwa;
      if (!runtime) throw new Error("MingLi Pyodide runtime is unavailable");
      await runtime.ready;

      const response = await fetch("/runtime/parity-reference.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`Unable to load parity reference (${response.status})`);
      const cases = (await response.json()) as ParityCase[];
      const outcomes: RuntimeOutcome[] = [];
      for (const parityCase of cases) {
        outcomes.push(await runtime.calculateOutcome(parityCase.input));
      }
      return { cases, outcomes };
    });

    expect(parity.cases).toHaveLength(154);
    expect(parity.outcomes).toHaveLength(parity.cases.length);

    for (const [index, parityCase] of parity.cases.entries()) {
      const actual = parity.outcomes[index];
      const expected = parityCase.outcome;
      expect(actual.ok, `${parityCase.id}: success/error status`).toBe(expected.ok);

      if (expected.ok) {
        if (!actual.ok) continue;
        expect(actual.result, `${parityCase.id}: canonical result`).toEqual(expected.result);
        expect(actual.canonical_hash, `${parityCase.id}: canonical hash`).toBe(expected.canonical_hash);
      } else {
        if (actual.ok) continue;
        expect(actual.error.code, `${parityCase.id}: ChartCalculationError.code`).toBe(
          parityCase.expected_error ?? expected.error.code,
        );
      }
    }
  });

  test("keeps pillars, luck, and canonical hash identical across 100 runs", async ({ page }) => {
    test.setTimeout(600_000);
    await openRuntime(page);

    const evidence = await page.evaluate(async () => {
      const runtime = (window as RuntimeWindow).__mingliPwa;
      if (!runtime) throw new Error("MingLi Pyodide runtime is unavailable");
      await runtime.ready;

      const response = await fetch("/runtime/parity-reference.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`Unable to load parity reference (${response.status})`);
      const cases = (await response.json()) as ParityCase[];
      const reference = cases.find((parityCase) => parityCase.outcome.ok);
      if (!reference || !reference.outcome.ok) throw new Error("Parity reference has no successful case");
      const summary = await runtime.determinism(reference.input, 100);
      return { expected: reference.outcome, summary };
    });

    expect(evidence.summary.runs).toBe(100);
    expect(evidence.summary.samples).toHaveLength(100);
    const first = evidence.summary.samples[0];
    expect(first.pillars).toEqual(evidence.expected.result.pillars);
    expect(first.luck).toEqual(evidence.expected.result.luck);
    expect(first.canonical_hash).toBe(evidence.expected.canonical_hash);

    for (const [index, sample] of evidence.summary.samples.entries()) {
      expect(sample.pillars, `run ${index + 1}: pillars`).toEqual(first.pillars);
      expect(sample.luck, `run ${index + 1}: luck`).toEqual(first.luck);
      expect(sample.canonical_hash, `run ${index + 1}: canonical hash`).toBe(first.canonical_hash);
    }
  });
});
