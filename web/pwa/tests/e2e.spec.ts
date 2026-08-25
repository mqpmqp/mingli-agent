import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Locator, type Page, type TestInfo } from "@playwright/test";

const RUNTIME_PROJECT = "mobile-390";
const APP_ORIGIN = "http://127.0.0.1:4173";
const PRIVATE_MARKER = "E2E-SYNTHETIC-PRIVATE-MARKER-48";
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "../../..");
const PYTHON = process.env.PWA_PYTHON ?? "python";

const SYNTHETIC_INPUT = {
  gender: "male",
  calendar: "solar",
  birth_date: "2000-01-07",
  birth_time: "12:00",
  timezone: "Asia/Shanghai",
  birth_location_note: PRIVATE_MARKER,
  longitude: "121.4737",
  latitude: "31.2304",
  true_solar_time: false,
  fold: "0",
};

const RESULT_FIELDS = [
  "civil-birth-time",
  "result-true-solar-time",
  "true-solar-correction-minutes",
  "equation-of-time-minutes",
  "year-pillar",
  "month-pillar",
  "day-pillar",
  "hour-pillar",
  "day-master",
  "luck-direction",
  "luck-start-age-raw",
  "luck-start-age-readable",
  "adjacent-solar-term",
  "adjacent-solar-term-time",
  "current-month-term",
  "method-id",
  "calculation-version",
  "git-sha",
  "wheel-sha256",
  "canonical-result-hash",
  "prediction-validity",
  "warnings",
] as const;

type ChartInput = {
  gender: string;
  calendar: string;
  birth_date: string;
  birth_time: string;
  timezone: string;
  birth_location_note?: string;
  longitude?: number | string | null;
  latitude?: number | string | null;
  true_solar_time?: boolean;
  is_leap_month?: boolean;
  fold?: number | string;
};

function useRuntimeProject(testInfo: TestInfo): void {
  test.skip(
    testInfo.project.name !== RUNTIME_PROJECT,
    "Pyodide/wheel initialization and real calculations run once on the canonical 390x844 mobile project.",
  );
  testInfo.setTimeout(180_000);
}

async function choose(page: Page, name: string, value: string): Promise<void> {
  const select = page.locator(`select[name="${name}"]`);
  if ((await select.count()) > 0) {
    const control = select.first();
    if (!(await control.isVisible())) {
      const summary = control.locator("xpath=ancestor::details[1]/summary[1]");
      if ((await summary.count()) > 0) await summary.click();
    }
    await control.selectOption(value);
    return;
  }

  const valuedControl = page.locator(`[name="${name}"][value="${value}"]`);
  if ((await valuedControl.count()) > 0) {
    const control = valuedControl.first();
    const type = await control.getAttribute("type");
    if (type === "radio" || type === "checkbox") {
      const label = control.locator("xpath=ancestor::label[1]");
      if ((await label.count()) > 0) {
        await label.click();
      } else {
        await control.check();
      }
      return;
    }
  }

  await page.locator(`[name="${name}"]`).first().fill(value);
}

async function setCheckbox(page: Page, name: string, checked: boolean): Promise<void> {
  const control = page.locator(`[name="${name}"]`).first();
  if (checked) {
    await control.check();
  } else {
    await control.uncheck();
  }
}

async function fillChartForm(page: Page, input: ChartInput = SYNTHETIC_INPUT): Promise<void> {
  await choose(page, "gender", input.gender);
  await choose(page, "calendar", input.calendar);
  if (input.calendar === "lunar") {
    const [year, month, day] = input.birth_date.split("-");
    await page.locator('[name="lunar_year"]').fill(String(Number(year)));
    await page.locator('[name="lunar_month"]').fill(String(Number(month)));
    await page.locator('[name="lunar_day"]').fill(String(Number(day)));
  } else {
    await page.locator('[name="birth_date"]').fill(input.birth_date);
  }
  await page.locator('[name="birth_time"]').fill(input.birth_time.slice(0, 5));
  await page.locator('[name="timezone"]').fill(input.timezone);

  const locationNote = page.locator('[name="birth_location_note"]');
  await locationNote.fill(input.birth_location_note ?? "");

  const longitude = page.locator('[name="longitude"]');
  if (input.longitude === null || input.longitude === undefined || input.longitude === "") {
    await longitude.fill("");
  } else {
    await longitude.fill(String(input.longitude));
  }

  const latitude = page.locator('[name="latitude"]');
  if (input.latitude === null || input.latitude === undefined || input.latitude === "") {
    await latitude.fill("");
  } else {
    await latitude.fill(String(input.latitude));
  }

  await setCheckbox(page, "true_solar_time", Boolean(input.true_solar_time));
  await choose(page, "fold", String(input.fold ?? 0));

  if (input.calendar === "lunar") {
    await setCheckbox(page, "is_leap_month", Boolean(input.is_leap_month));
  }

  await setCheckbox(page, "coordinate_confirm", true);
}

async function submitChart(page: Page): Promise<void> {
  await page.locator('#chart-form button[type="submit"]').click();
}

function formAlert(page: Page) {
  return page
    .locator(
      '#chart-form [data-testid="form-error"], #chart-form [data-testid="form-errors"], #chart-form [role="alert"]',
    )
    .first();
}

async function expectFormError(page: Page, message: RegExp): Promise<void> {
  const alert = formAlert(page);
  await expect(alert).toBeVisible();
  await expect(alert).toContainText(message);
  await expect(page.getByTestId("result-section")).toBeHidden();
}

async function waitForRuntimeReady(page: Page): Promise<void> {
  const status = page.getByTestId("runtime-status");
  await expect(status).toContainText(/已就绪|可以排盘|可离线排盘/, { timeout: 120_000 });
}

async function tabTo(page: Page, target: Locator, limit = 60): Promise<void> {
  for (let index = 0; index < limit; index += 1) {
    await page.keyboard.press("Tab");
    if (await target.evaluate((element) => element === document.activeElement)) return;
  }
  throw new Error(`Tab could not reach ${await target.evaluate((element) => element.outerHTML)}`);
}

async function keyboardFill(page: Page, target: Locator, value: string): Promise<void> {
  await tabTo(page, target);
  await page.keyboard.press("Control+A");
  await page.keyboard.press("Backspace");
  await target.fill(value);
}

function calculateWithCPython(input: ChartInput): Record<string, unknown> {
  const script = [
    "import json, sys",
    "from mingli.bazi import DeterministicBaziEngine",
    "result = DeterministicBaziEngine().calculate(json.loads(sys.argv[1]))",
    "print(json.dumps(result, ensure_ascii=False, sort_keys=True))",
  ].join("\n");
  return JSON.parse(
    execFileSync(PYTHON, ["-X", "utf8", "-c", script, JSON.stringify(input)], {
      cwd: REPO_ROOT,
      encoding: "utf8",
    }),
  ) as Record<string, unknown>;
}

async function renderedEngineResult(page: Page): Promise<Record<string, unknown>> {
  const presentation = JSON.parse(await page.getByTestId("result-json").inputValue()) as {
    result: Record<string, unknown>;
  };
  return presentation.result;
}

test.describe("mobile privacy-first shell", () => {
  test("shows the local-only contract, the complete form, and no horizontal overflow", async ({ page }) => {
    await page.route("**/runtime/**", (route) => route.abort("failed"));
    await page.goto("/");

    await expect(page.getByText("本地计算，出生资料未上传", { exact: true })).toBeVisible();
    const form = page.locator("#chart-form");
    await expect(form).toBeVisible();
    await page.locator("details.advanced-options > summary").click();
    await expect(page.getByTestId("runtime-status")).toBeVisible();

    for (const name of [
      "gender",
      "calendar",
      "birth_date",
      "birth_time",
      "timezone",
      "birth_location_note",
      "longitude",
      "latitude",
      "true_solar_time",
      "fold",
      "coordinate_confirm",
    ]) {
      await expect(page.locator(`[name="${name}"]`).first(), `${name} should be visible`).toBeVisible();
    }

    const dimensions = await page.evaluate(() => ({
      bodyClientWidth: document.body.clientWidth,
      bodyScrollWidth: document.body.scrollWidth,
      rootClientWidth: document.documentElement.clientWidth,
      rootScrollWidth: document.documentElement.scrollWidth,
    }));
    expect(dimensions.bodyScrollWidth).toBeLessThanOrEqual(dimensions.bodyClientWidth);
    expect(dimensions.rootScrollWidth).toBeLessThanOrEqual(dimensions.rootClientWidth);
  });

  test("shows and submits the leap-month field only for lunar input", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== RUNTIME_PROJECT, "One project is enough for form-state behavior.");
    await page.route("**/runtime/**", (route) => route.abort("failed"));
    await page.goto("/");

    const leapMonth = page.locator('[name="is_leap_month"]');
    await expect(leapMonth).toBeHidden();

    await choose(page, "calendar", "lunar");
    await expect(leapMonth).toBeVisible();
    await expect(leapMonth).toBeEnabled();
    await leapMonth.check();

    await choose(page, "calendar", "solar");
    await expect(leapMonth).toBeHidden();
    const formHasLeapMonth = await page.locator("#chart-form").evaluate((form) =>
      new FormData(form as HTMLFormElement).has("is_leap_month"),
    );
    expect(formHasLeapMonth).toBe(false);
  });

  test("uses independent numeric lunar year month day controls without Gregorian date semantics", async ({
    page,
  }, testInfo) => {
    test.skip(testInfo.project.name !== RUNTIME_PROJECT, "One project is enough for form-state behavior.");
    await page.route("**/runtime/**", (route) => route.abort("failed"));
    await page.goto("/");

    await choose(page, "calendar", "lunar");
    await expect(page.getByTestId("birth-date")).toBeHidden();
    await expect(page.getByTestId("birth-date")).toBeDisabled();

    for (const [name, minimum, maximum] of [
      ["lunar_year", "1901", "2099"],
      ["lunar_month", "1", "12"],
      ["lunar_day", "1", "30"],
    ] as const) {
      const control = page.locator(`[name="${name}"]`);
      await expect(control).toBeVisible();
      await expect(control).toBeEnabled();
      await expect(control).toHaveAttribute("type", "number");
      await expect(control).toHaveAttribute("min", minimum);
      await expect(control).toHaveAttribute("max", maximum);
    }

    await page.locator('[name="lunar_year"]').fill("2023");
    await page.locator('[name="lunar_month"]').fill("2");
    await page.locator('[name="lunar_day"]').fill("29");
    expect(
      await page
        .locator('[name="lunar_day"]')
        .evaluate((element) => (element as HTMLInputElement).checkValidity()),
    ).toBe(true);
  });

  test("requires coordinates to be confirmed again after either value changes", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== RUNTIME_PROJECT, "One project is enough for form-state behavior.");
    await page.route("**/runtime/**", (route) => route.abort("failed"));
    await page.goto("/");

    const confirmation = page.locator('[name="coordinate_confirm"]');
    await page.locator('[name="longitude"]').fill(SYNTHETIC_INPUT.longitude);
    await page.locator('[name="latitude"]').fill(SYNTHETIC_INPUT.latitude);
    await confirmation.check();

    await page.locator('[name="longitude"]').fill("120.5");
    await expect(confirmation).not.toBeChecked();

    await confirmation.check();
    await page.locator('[name="latitude"]').fill("30.5");
    await expect(confirmation).not.toBeChecked();
  });
});

test.describe("form validation", () => {
  test("rejects missing fields, unconfirmed coordinates, true-solar input without longitude, ranges, and bad timezones", async ({
    page,
  }, testInfo) => {
    useRuntimeProject(testInfo);
    await page.goto("/");
    await waitForRuntimeReady(page);
    await fillChartForm(page);

    await test.step("required birth fields", async () => {
      await page.locator('[name="birth_date"]').fill("");
      await submitChart(page);
      await expectFormError(page, /出生日期.*(?:必填|填写)|(?:必填|填写).*出生日期/);
      await page.locator('[name="birth_date"]').fill(SYNTHETIC_INPUT.birth_date);
    });

    await test.step("explicit coordinate confirmation", async () => {
      await setCheckbox(page, "coordinate_confirm", false);
      await submitChart(page);
      await expectFormError(page, /确认.*(?:经度|纬度|坐标)|坐标.*确认/);
      await setCheckbox(page, "coordinate_confirm", true);
    });

    await test.step("longitude required for true solar time", async () => {
      await setCheckbox(page, "true_solar_time", true);
      await page.locator('[name="longitude"]').fill("");
      await submitChart(page);
      await expectFormError(page, /真太阳时.*经度|经度.*真太阳时/);
    });

    await test.step("coordinate boundaries", async () => {
      await page.locator('[name="longitude"]').fill("180.0001");
      await submitChart(page);
      await expectFormError(page, /经度.*(?:-180|180)|(?:-180|180).*经度/);

      await page.locator('[name="longitude"]').fill(SYNTHETIC_INPUT.longitude);
      await page.locator('[name="latitude"]').fill("-90.0001");
      await submitChart(page);
      await expectFormError(page, /纬度.*(?:-90|90)|(?:-90|90).*纬度/);
    });

    await test.step("IANA timezone", async () => {
      await setCheckbox(page, "true_solar_time", false);
      await page.locator('[name="latitude"]').fill(SYNTHETIC_INPUT.latitude);
      await page.locator('[name="timezone"]').fill("Invalid/Timezone");
      await submitChart(page);
      await expectFormError(page, /时区.*(?:无效|不存在|IANA)|(?:无效|不存在|IANA).*时区/);
      await expect(formAlert(page)).not.toContainText("INVALID_TIMEZONE");
    });
  });
});

test.describe("keyboard and accessible error recovery", () => {
  test("moves keyboard focus to an alert summary and links then clears invalid field state", async ({
    page,
  }, testInfo) => {
    useRuntimeProject(testInfo);
    await page.goto("/");
    await waitForRuntimeReady(page);

    const calculate = page.getByTestId("calculate");
    await tabTo(page, calculate);
    await page.keyboard.press("Enter");

    const alert = page.getByTestId("form-error");
    const birthDate = page.getByTestId("birth-date");
    await expect(alert).toBeVisible();
    await expect(alert).toBeFocused();
    await expect(alert).toHaveAttribute("tabindex", "-1");
    await expect(alert).toHaveAttribute("role", "alert");
    await expect(alert).toHaveAttribute("aria-live", /assertive|polite/);
    await expect(birthDate).toHaveAttribute("aria-invalid", "true");
    await expect(birthDate).toHaveAttribute("aria-describedby", /form-error/);

    await tabTo(page, birthDate);
    await birthDate.fill(SYNTHETIC_INPUT.birth_date);
    await expect(birthDate).not.toHaveAttribute("aria-invalid", "true");
    await expect(birthDate).not.toHaveAttribute("aria-describedby", /form-error/);
  });

  test("completes a solar calculation, result action, and clear using keyboard navigation", async ({
    context,
    page,
  }, testInfo) => {
    useRuntimeProject(testInfo);
    await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: APP_ORIGIN });
    await page.goto("/");
    await waitForRuntimeReady(page);

    const genderMale = page.getByTestId("gender-male");
    await tabTo(page, genderMale);
    await page.keyboard.press("ArrowRight");
    await expect(page.getByTestId("gender-female")).toBeChecked();

    const calendarSolar = page.getByTestId("calendar-solar");
    await tabTo(page, calendarSolar);
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("ArrowLeft");
    await expect(calendarSolar).toBeChecked();

    await keyboardFill(page, page.getByTestId("birth-date"), SYNTHETIC_INPUT.birth_date);
    await keyboardFill(page, page.getByTestId("birth-time"), SYNTHETIC_INPUT.birth_time);
    await keyboardFill(page, page.getByTestId("timezone"), SYNTHETIC_INPUT.timezone);
    await keyboardFill(page, page.getByTestId("location-note"), "KEYBOARD_SOLAR_NOTE_48");
    await keyboardFill(page, page.getByTestId("longitude"), SYNTHETIC_INPUT.longitude);
    await keyboardFill(page, page.getByTestId("latitude"), SYNTHETIC_INPUT.latitude);

    await tabTo(page, page.getByTestId("true-solar-time"));
    await page.keyboard.press("Space");
    await expect(page.getByTestId("true-solar-time")).toBeChecked();

    const advanced = page.locator("details.advanced-options > summary");
    await tabTo(page, advanced);
    await page.keyboard.press("Enter");
    const fold = page.locator('[name="fold"]');
    await tabTo(page, fold);
    await page.keyboard.press("ArrowDown");
    await expect(fold).toHaveValue("1");

    await tabTo(page, page.getByTestId("coordinate-confirm"));
    await page.keyboard.press("Space");
    await tabTo(page, page.getByTestId("calculate"));
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("result-section")).toBeVisible({ timeout: 60_000 });

    await tabTo(page, page.getByTestId("copy-summary"));
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("action-feedback")).toContainText(/复制/u);
    await tabTo(page, page.getByTestId("clear-data"));
    await page.keyboard.press("Enter");

    await expect(page.getByTestId("result-section")).toBeHidden();
    await expect(page.getByTestId("form-error")).toBeHidden();
    await expect(genderMale).toBeFocused();
    await expect(page.getByTestId("birth-date")).toHaveValue("");
  });

  test("completes a lunar leap-month calculation and clears new controls using the keyboard", async ({
    context,
    page,
  }, testInfo) => {
    useRuntimeProject(testInfo);
    await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: APP_ORIGIN });
    await page.goto("/");
    await waitForRuntimeReady(page);

    await tabTo(page, page.getByTestId("gender-male"));
    await page.keyboard.press("ArrowRight");
    await tabTo(page, page.getByTestId("calendar-solar"));
    await page.keyboard.press("ArrowRight");
    await expect(page.getByTestId("calendar-lunar")).toBeChecked();

    await keyboardFill(page, page.getByTestId("lunar-year"), "2023");
    await keyboardFill(page, page.getByTestId("lunar-month"), "2");
    await keyboardFill(page, page.getByTestId("lunar-day"), "29");
    await keyboardFill(page, page.getByTestId("birth-time"), "12:00");
    await keyboardFill(page, page.getByTestId("timezone"), "Asia/Shanghai");
    await keyboardFill(page, page.getByTestId("location-note"), "KEYBOARD_LUNAR_NOTE_48");
    await keyboardFill(page, page.getByTestId("longitude"), "121.4737");
    await keyboardFill(page, page.getByTestId("latitude"), "31.2304");

    await tabTo(page, page.getByTestId("true-solar-time"));
    await page.keyboard.press("Space");
    const leapMonth = page.locator('[name="is_leap_month"]');
    await tabTo(page, leapMonth);
    await page.keyboard.press("Space");
    await expect(leapMonth).toBeChecked();

    const advanced = page.locator("details.advanced-options > summary");
    await tabTo(page, advanced);
    await page.keyboard.press("Enter");
    const fold = page.locator('[name="fold"]');
    await tabTo(page, fold);
    await page.keyboard.press("ArrowDown");
    await expect(fold).toHaveValue("1");

    await tabTo(page, page.getByTestId("coordinate-confirm"));
    await page.keyboard.press("Space");
    await tabTo(page, page.getByTestId("calculate"));
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("result-section")).toBeVisible({ timeout: 60_000 });

    await tabTo(page, page.getByTestId("copy-json"));
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("action-feedback")).toContainText(/复制/u);
    await tabTo(page, page.getByTestId("clear-data"));
    await page.keyboard.press("Enter");

    await expect(page.getByTestId("result-section")).toBeHidden();
    await expect(page.getByTestId("lunar-year")).toHaveValue("");
    await expect(page.getByTestId("lunar-month")).toHaveValue("");
    await expect(page.getByTestId("lunar-day")).toHaveValue("");
    await expect(page.getByTestId("gender-male")).toBeFocused();
  });
});

test.describe("runtime lifecycle", () => {
  test("reports Pyodide initialization and reaches the ready state", async ({ page }, testInfo) => {
    useRuntimeProject(testInfo);
    await page.goto("/");

    const status = page.getByTestId("runtime-status");
    await expect(status).toContainText(/正在.*(?:初始化|加载)|准备.*运行环境/);
    await waitForRuntimeReady(page);
  });

  test("shows an actionable retry when runtime initialization fails", async ({ page }, testInfo) => {
    useRuntimeProject(testInfo);
    let attempts = 0;
    await page.route("**/runtime/runtime-manifest.json", async (route) => {
      attempts += 1;
      await route.abort("failed");
    });

    await page.goto("/");
    const status = page.getByTestId("runtime-status");
    await expect(status).toContainText(/初始化失败|运行环境.*加载失败|无法加载.*运行资源/);

    const retry = page.getByTestId("retry-runtime");
    await expect(retry).toBeVisible();
    await expect(retry).toBeEnabled();
    await retry.click();
    await expect.poll(() => attempts, { timeout: 15_000 }).toBeGreaterThan(1);
  });

  test("distinguishes repository wheel installation failure and offers retry", async ({ page }, testInfo) => {
    useRuntimeProject(testInfo);
    await page.addInitScript(() => {
      Object.defineProperty(navigator, "serviceWorker", {
        configurable: true,
        value: {
          controller: null,
          register: async () => {
            throw new Error("service worker disabled for wheel-failure isolation");
          },
        },
      });
    });

    let wheelRequests = 0;
    await page.route(/\/runtime\/packages\/mingli_agent-.*\.whl(?:\?.*)?$/, async (route) => {
      wheelRequests += 1;
      await route.abort("failed");
    });

    await page.goto("/");
    await expect.poll(() => wheelRequests, { timeout: 120_000 }).toBeGreaterThan(0);
    await expect(page.getByTestId("runtime-status")).toContainText(
      /排盘引擎.*加载失败|核心程序.*加载失败|wheel.*失败|运行资源.*加载失败/i,
    );
    await expect(page.getByTestId("retry-runtime")).toBeVisible();
  });
});

test.describe("real deterministic chart journey", () => {
  test("submits lunar 2023 leap month day 29 through the visible UI and matches CPython", async ({
    page,
  }, testInfo) => {
    useRuntimeProject(testInfo);
    const input: ChartInput = {
      ...SYNTHETIC_INPUT,
      calendar: "lunar",
      birth_date: "2023-02-29",
      is_leap_month: true,
    };
    const expected = calculateWithCPython(input);

    await page.goto("/");
    await waitForRuntimeReady(page);
    await fillChartForm(page, input);
    await submitChart(page);

    await expect(page.getByTestId("result-section")).toBeVisible({ timeout: 60_000 });
    expect(await renderedEngineResult(page)).toEqual(expected);
    for (const pillar of ["year-pillar", "month-pillar", "day-pillar", "hour-pillar"]) {
      await expect(page.getByTestId(pillar)).toHaveText(/[\u3400-\u9fff]{2}/u);
    }
  });

  test("submits structurally valid lunar day 30 to the engine and shows INVALID_LUNAR_DATE safely", async ({
    page,
  }, testInfo) => {
    useRuntimeProject(testInfo);
    await page.goto("/");
    await waitForRuntimeReady(page);
    await fillChartForm(page, {
      ...SYNTHETIC_INPUT,
      calendar: "lunar",
      birth_date: "2023-02-30",
      is_leap_month: true,
    });
    await submitChart(page);

    const error = page.getByTestId("calculation-error");
    await expect(error).toBeVisible({ timeout: 60_000 });
    await expect(error).toContainText(/农历.*(?:月份|日期).*无效|(?:月份|日期).*闰月/u);
    await expect(error).toContainText(/检查.*月份.*日期.*闰月/u);
    await expect(error).not.toContainText("INVALID_LUNAR_DATE");
    await expect(page.getByTestId("result-section")).toBeHidden();
    for (const pillar of ["year-pillar", "month-pillar", "day-pillar", "hour-pillar"]) {
      await expect(page.getByTestId(pillar)).toBeHidden();
    }
  });

  test("submits an ordinary non-leap lunar date through the visible UI", async ({ page }, testInfo) => {
    useRuntimeProject(testInfo);
    const input: ChartInput = {
      ...SYNTHETIC_INPUT,
      calendar: "lunar",
      birth_date: "2023-01-15",
      is_leap_month: false,
    };

    await page.goto("/");
    await waitForRuntimeReady(page);
    await fillChartForm(page, input);
    await submitChart(page);

    await expect(page.getByTestId("result-section")).toBeVisible({ timeout: 60_000 });
    expect(await renderedEngineResult(page)).toEqual(calculateWithCPython(input));
  });

  test("renders every required result and supports copy, download, prompt, and privacy-safe clear", async ({
    context,
    page,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: APP_ORIGIN });
    await page.goto("/");
    await waitForRuntimeReady(page);
    await fillChartForm(page);
    await submitChart(page);

    const result = page.getByTestId("result-section");
    await expect(result).toBeVisible({ timeout: 60_000 });
    for (const field of RESULT_FIELDS) {
      const output = result.getByTestId(field);
      await expect(output, `${field} should be rendered`).toBeVisible();
      await expect(output, `${field} should not be blank`).not.toHaveText(/^\s*$/);
    }
    for (const pillar of ["year-pillar", "month-pillar", "day-pillar", "hour-pillar"]) {
      await expect(result.getByTestId(pillar)).toContainText(/[\u3400-\u9fff]{2}/);
    }
    await expect(result.getByTestId("git-sha")).toContainText(/[0-9a-f]{40}/i);
    await expect(result.getByTestId("wheel-sha256")).toContainText(/[0-9a-f]{64}/i);
    await expect(result.getByTestId("canonical-result-hash")).toContainText(/sha256:[0-9a-f]{64}/i);

    await page.getByTestId("copy-summary").click();
    const summary = await page.evaluate(() => navigator.clipboard.readText());
    expect(summary).toMatch(/年柱|四柱/);
    expect(summary).toContain("method_id");

    await page.getByTestId("copy-json").click();
    const copiedJsonText = await page.evaluate(() => navigator.clipboard.readText());
    expect(copiedJsonText).not.toContain(PRIVATE_MARKER);
    const copiedJson = JSON.parse(copiedJsonText) as Record<string, unknown>;
    expect(copiedJson.result).toMatchObject({
      method_id: expect.any(String),
      pillars: expect.any(Object),
    });

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByTestId("download-json").click(),
    ]);
    expect(download.suggestedFilename()).toMatch(/\.json$/i);
    const downloadedPath = await download.path();
    expect(downloadedPath).not.toBeNull();
    const downloadedJsonText = await readFile(downloadedPath!, "utf8");
    expect(downloadedJsonText).not.toContain(PRIVATE_MARKER);
    const downloadedJson = JSON.parse(downloadedJsonText) as Record<string, unknown>;
    expect(downloadedJson).toEqual(copiedJson);

    await page.getByTestId("copy-prompt").click();
    const prompt = await page.evaluate(() => navigator.clipboard.readText());
    expect(prompt).toMatch(/ChatGPT|解读/);
    expect(prompt).toContain("method_id");
    expect(prompt).toContain("calculation_version");
    expect(prompt).not.toContain(PRIVATE_MARKER);

    await page.getByTestId("clear-data").click();
    await expect(result).toBeHidden();
    await expect(page.locator('[name="birth_date"]')).toHaveValue("");
    await expect(page.locator('[name="birth_time"]')).toHaveValue("");
    await expect(page.locator('[name="birth_location_note"]')).toHaveValue("");
    await expect(page.locator('[name="longitude"]')).toHaveValue("");
    await expect(page.locator('[name="latitude"]')).toHaveValue("");
    await expect(page.locator('[name="coordinate_confirm"]')).not.toBeChecked();

    const sensitiveResidue = await page.evaluate(async (needles) => {
      const serializedForm = JSON.stringify(
        Array.from(new FormData(document.querySelector<HTMLFormElement>("#chart-form")!).entries()),
      );
      const dom = `${document.documentElement.outerHTML}\n${document.body.innerText}\n${serializedForm}`;
      const local = JSON.stringify(
        Array.from({ length: localStorage.length }, (_, index) => {
          const key = localStorage.key(index) ?? "";
          return [key, localStorage.getItem(key)];
        }),
      );
      const session = JSON.stringify(
        Array.from({ length: sessionStorage.length }, (_, index) => {
          const key = sessionStorage.key(index) ?? "";
          return [key, sessionStorage.getItem(key)];
        }),
      );
      const databaseNames = "databases" in indexedDB
        ? (await indexedDB.databases()).map((database) => database.name ?? "")
        : [];
      const find = (haystack: string) => needles.filter((needle) => haystack.includes(needle));
      return {
        dom: find(dom),
        localStorage: find(local),
        sessionStorage: find(session),
        databaseNames,
      };
    }, [PRIVATE_MARKER, SYNTHETIC_INPUT.birth_date, SYNTHETIC_INPUT.birth_time, SYNTHETIC_INPUT.longitude, SYNTHETIC_INPUT.latitude]);

    expect(sensitiveResidue.dom).toEqual([]);
    expect(sensitiveResidue.localStorage).toEqual([]);
    expect(sensitiveResidue.sessionStorage).toEqual([]);
    expect(sensitiveResidue.databaseNames).toEqual([]);
  });

  test("fails closed on SOLAR_TERM_UNCERTAIN with REVIEW_REQUIRED and no pillars", async ({
    page,
    request,
  }, testInfo) => {
    useRuntimeProject(testInfo);
    const response = await request.get("/runtime/parity-reference.json");
    expect(response.ok()).toBe(true);
    const cases = (await response.json()) as Array<{
      input: ChartInput;
      outcome: { ok: boolean; error?: { code?: string } };
    }>;
    const uncertain = cases.find((item) => item.outcome.error?.code === "SOLAR_TERM_UNCERTAIN");
    expect(uncertain, "generated parity corpus must include SOLAR_TERM_UNCERTAIN").toBeTruthy();

    await page.goto("/");
    await waitForRuntimeReady(page);
    await fillChartForm(page, uncertain!.input);
    await submitChart(page);

    const error = page.getByTestId("calculation-error");
    await expect(error).toBeVisible({ timeout: 60_000 });
    await expect(error).toContainText("REVIEW_REQUIRED");
    await expect(error).toContainText(/节气.*边界|人工复核|无法确定/);
    await expect(error).not.toContainText("SOLAR_TERM_UNCERTAIN");
    await expect(page.getByTestId("result-section")).toBeHidden();
    for (const pillar of ["year-pillar", "month-pillar", "day-pillar", "hour-pillar"]) {
      await expect(page.getByTestId(pillar)).toBeHidden();
    }
  });

  test("invalidates a rendered result as soon as the form input changes", async ({ page }, testInfo) => {
    useRuntimeProject(testInfo);
    await page.goto("/");
    await waitForRuntimeReady(page);
    await fillChartForm(page);
    await submitChart(page);

    const result = page.getByTestId("result-section");
    await expect(result).toBeVisible({ timeout: 60_000 });
    await page.locator('[name="birth_location_note"]').fill("已修改，旧结果不得继续导出");

    await expect(result).toBeHidden();
    await expect(page.getByTestId("result-json")).toHaveValue("");
    await expect(page.getByTestId("action-feedback")).toHaveText("");
  });

  test("keeps the cleared state final when an earlier clipboard write settles late", async ({ page }, testInfo) => {
    useRuntimeProject(testInfo);
    await page.goto("/");
    await waitForRuntimeReady(page);
    await fillChartForm(page);
    await submitChart(page);
    await expect(page.getByTestId("result-section")).toBeVisible({ timeout: 60_000 });

    await page.evaluate(() => {
      let resolveWrite: () => void = () => undefined;
      const pendingWrite = new Promise<void>((resolve) => {
        resolveWrite = resolve;
      });
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: { writeText: () => pendingWrite },
      });
      Object.defineProperty(window, "__resolveClipboardWrite", {
        configurable: true,
        value: resolveWrite,
      });
    });

    await page.getByTestId("copy-summary").click();
    await page.getByTestId("clear-data").click();
    await page.evaluate(() => {
      (window as typeof window & { __resolveClipboardWrite: () => void }).__resolveClipboardWrite();
    });

    await expect(page.getByTestId("result-section")).toBeHidden();
    await expect(page.getByTestId("action-feedback")).toHaveText("");
  });

  test("keeps the cleared state final when an earlier calculation settles late", async ({ page }, testInfo) => {
    useRuntimeProject(testInfo);
    await page.goto("/");
    await waitForRuntimeReady(page);
    await fillChartForm(page);

    await page.evaluate(() => {
      const form = document.querySelector<HTMLFormElement>("#chart-form");
      const clearButton = document.querySelector<HTMLButtonElement>('[data-testid="clear-data"]');
      if (!form || !clearButton) throw new Error("测试页面缺少表单或清空按钮");
      form.requestSubmit();
      queueMicrotask(() => clearButton.click());
    });

    await expect(page.getByTestId("result-section")).toBeHidden({ timeout: 60_000 });
    await expect(page.getByTestId("result-json")).toHaveValue("");
    await expect(page.locator('[name="birth_date"]')).toHaveValue("");
  });
});

test.describe("PWA update experience", () => {
  test("shows an update banner when an installed service worker reports a new version", async ({
    page,
  }, testInfo) => {
    test.skip(testInfo.project.name !== RUNTIME_PROJECT, "One project is enough for service-worker event wiring.");
    await page.addInitScript(() => {
      const pageLoadCount = Number(sessionStorage.getItem("__pwaPageLoadCount") ?? "0") + 1;
      sessionStorage.setItem("__pwaPageLoadCount", String(pageLoadCount));

      const installing = Object.assign(new EventTarget(), {
        state: "installing",
        postMessage: (message: unknown) => {
          window.name = JSON.stringify(message);
          serviceWorker.dispatchEvent(new Event("controllerchange"));
        },
      });
      const registration = Object.assign(new EventTarget(), {
        active: {},
        installing,
        waiting: null,
        scope: `${location.origin}/`,
        update: async () => undefined,
        unregister: async () => true,
      });
      const serviceWorker = Object.assign(new EventTarget(), {
        controller: {},
        ready: Promise.resolve(registration),
        getRegistration: async () => registration,
        getRegistrations: async () => [registration],
        register: async () => {
          Object.defineProperty(window, "__pwaRegistrationObserved", {
            configurable: true,
            value: true,
          });
          return registration;
        },
      });
      Object.defineProperty(navigator, "serviceWorker", {
        configurable: true,
        value: serviceWorker,
      });
      Object.defineProperty(window, "__emitPwaUpdate", {
        configurable: true,
        value: () => {
          registration.dispatchEvent(new Event("updatefound"));
          installing.state = "installed";
          Object.defineProperty(registration, "waiting", {
            configurable: true,
            value: installing,
          });

          installing.dispatchEvent(new Event("statechange"));
        },
      });
    });
    await page.route("**/runtime/**", (route) => route.abort("failed"));
    await page.goto("/");
    const initialPageLoadCount = await page.evaluate(
      () => Number(sessionStorage.getItem("__pwaPageLoadCount") ?? "0"),
    );
    await expect
      .poll(() =>
        page.evaluate(() =>
          Boolean((window as Window & { __pwaRegistrationObserved?: boolean }).__pwaRegistrationObserved),
        ),
      )
      .toBe(true);

    await page.evaluate(() => (window as unknown as Window & { __emitPwaUpdate: () => void }).__emitPwaUpdate());
    const banner = page.getByTestId("update-banner");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText(/新版本|更新/);
    await page.locator('[data-action="reload-app"]').click();
    await expect.poll(() => page.evaluate(() => window.name)).toBe(JSON.stringify({ type: "SKIP_WAITING" }));
    await expect
      .poll(() => page.evaluate(() => Number(sessionStorage.getItem("__pwaPageLoadCount") ?? "0")))
      .toBeGreaterThan(initialPageLoadCount);
  });
});
