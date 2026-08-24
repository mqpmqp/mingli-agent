import { expect, test, type Locator, type Page, type TestInfo } from "@playwright/test";

type WebAppManifest = {
  name?: string;
  short_name?: string;
  start_url?: string;
  display?: string;
  icons?: Array<{
    src?: string;
    sizes?: string;
    type?: string;
    purpose?: string;
  }>;
};

type MetricName =
  | "FIRST_LOAD_MS"
  | "FIRST_INIT_MS"
  | "FIRST_CALC_MS"
  | "SECOND_LOAD_MS"
  | "SECOND_CALC_MS";

type ObservedRequest = {
  method: string;
  resourceType: string;
  url: string;
  postData: string | null;
};

const APP_PATH = "/";
const MANIFEST_PATH = "/manifest.webmanifest";
const METRIC_NAMES: MetricName[] = [
  "FIRST_LOAD_MS",
  "FIRST_INIT_MS",
  "FIRST_CALC_MS",
  "SECOND_LOAD_MS",
  "SECOND_CALC_MS",
];

const SYNTHETIC_INPUT = {
  gender: "male",
  calendar: "solar",
  birthDate: "2000-01-07",
  birthTime: "12:00",
  timezone: "Asia/Shanghai",
  locationNote: "PW_PRIVACY_SENTINEL_7f3a9c2e",
  longitude: "121.4737",
  latitude: "31.2304",
  trueSolarTime: true,
} as const;

// Stable mobile E2E contract. The app should expose state through the DOM rather
// than requiring tests to call its internal runtime or calculation objects.
const MOBILE_E2E = {
  appShell: (page: Page) => page.getByTestId("mingli-app"),
  runtimeStatus: (page: Page) => page.getByTestId("runtime-status"),
  offlineReady: (page: Page) => page.getByTestId("offline-ready"),
  genderMale: (page: Page) => page.getByTestId("gender-male"),
  calendarSolar: (page: Page) => page.getByTestId("calendar-solar"),
  birthDate: (page: Page) => page.getByTestId("birth-date"),
  birthTime: (page: Page) => page.getByTestId("birth-time"),
  timezone: (page: Page) => page.getByTestId("timezone"),
  locationNote: (page: Page) => page.getByTestId("location-note"),
  longitude: (page: Page) => page.getByTestId("longitude"),
  latitude: (page: Page) => page.getByTestId("latitude"),
  trueSolarTime: (page: Page) => page.getByTestId("true-solar-time"),
  coordinateConfirm: (page: Page) => page.getByTestId("coordinate-confirm"),
  calculate: (page: Page) => page.getByTestId("calculate"),
  result: (page: Page) => page.getByTestId("result"),
  resultJson: (page: Page) => page.getByTestId("result-json"),
  resultHash: (page: Page) => page.getByTestId("canonical-result-hash"),
} as const;

const STATIC_CACHE_PATHS = [
  /^\/$/,
  /^\/index\.html$/,
  /^\/manifest\.webmanifest$/,
  /^\/(?:service-worker|sw)\.js$/,
  /^\/(?:icon|favicon|apple-touch-icon)[^/]*\.(?:ico|png|svg|webp)$/,
  /^\/icons\//,
  /^\/assets\//,
  /^\/runtime\//,
  /^\/src\//,
  /^\/@vite\//,
  /^\/@id\//,
  /^\/node_modules\/\.vite\//,
];

async function attachJson(testInfo: TestInfo, name: string, value: unknown): Promise<void> {
  await testInfo.attach(name, {
    body: Buffer.from(`${JSON.stringify(value, null, 2)}\n`, "utf8"),
    contentType: "application/json",
  });
}

async function attachMetrics(testInfo: TestInfo, metrics: Partial<Record<MetricName, number>>): Promise<void> {
  const report = Object.fromEntries(METRIC_NAMES.map((name) => [name, metrics[name] ?? null]));
  await attachJson(testInfo, "pwa-performance-metrics", report);
  for (const name of METRIC_NAMES) {
    console.log(`${name}=${metrics[name] ?? "NOT_RECORDED"}`);
  }
}

async function fillSyntheticInput(page: Page): Promise<void> {
  await MOBILE_E2E.genderMale(page).check();
  await MOBILE_E2E.calendarSolar(page).check();
  await MOBILE_E2E.birthDate(page).fill(SYNTHETIC_INPUT.birthDate);
  await MOBILE_E2E.birthTime(page).fill(SYNTHETIC_INPUT.birthTime);
  await MOBILE_E2E.timezone(page).fill(SYNTHETIC_INPUT.timezone);
  await MOBILE_E2E.locationNote(page).fill(SYNTHETIC_INPUT.locationNote);
  await MOBILE_E2E.longitude(page).fill(SYNTHETIC_INPUT.longitude);
  await MOBILE_E2E.latitude(page).fill(SYNTHETIC_INPUT.latitude);
  await MOBILE_E2E.trueSolarTime(page).check();
  await MOBILE_E2E.coordinateConfirm(page).check();
}

async function textOrValue(locator: Locator): Promise<string> {
  return locator.evaluate((element) => {
    if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) return element.value;
    return element.textContent ?? "";
  });
}

async function calculateAndReadResult(page: Page): Promise<{ canonicalResult: unknown; hash: string }> {
  await MOBILE_E2E.calculate(page).click();
  await expect(MOBILE_E2E.result(page)).toBeVisible({ timeout: 120_000 });
  await expect(MOBILE_E2E.resultJson(page)).toHaveCount(1);
  await expect(MOBILE_E2E.resultHash(page)).toHaveText(/^sha256:[0-9a-f]{64}$/, { timeout: 120_000 });

  const resultJson = (await textOrValue(MOBILE_E2E.resultJson(page))).trim();
  expect(resultJson).not.toBe("");
  const canonicalResult = JSON.parse(resultJson) as unknown;
  const hash = (await MOBILE_E2E.resultHash(page).innerText()).trim();
  return { canonicalResult, hash };
}

async function storageAudit(page: Page): Promise<{
  localStorageKeys: string[];
  sessionStorageKeys: string[];
  indexedDbNames: Array<string | null>;
}> {
  return page.evaluate(async () => ({
    localStorageKeys: Object.keys(localStorage),
    sessionStorageKeys: Object.keys(sessionStorage),
    indexedDbNames: (await indexedDB.databases()).map((database) => database.name ?? null),
  }));
}

function expectNoPersistentUserData(audit: Awaited<ReturnType<typeof storageAudit>>): void {
  expect(audit.localStorageKeys).toEqual([]);
  expect(audit.sessionStorageKeys).toEqual([]);
  expect(audit.indexedDbNames).toEqual([]);
}

async function cacheStorageAudit(page: Page, sensitiveValues: string[]) {
  return page.evaluate(async ({ values }) => {
    const cacheNames = await caches.keys();
    const entries: Array<{
      cacheName: string;
      url: string;
      method: string;
      contentType: string;
      sensitiveMatches: string[];
      readError: string | null;
    }> = [];

    for (const cacheName of cacheNames) {
      const cache = await caches.open(cacheName);
      for (const request of await cache.keys()) {
        const response = await cache.match(request);
        const contentType = response?.headers.get("content-type") ?? "";
        let sensitiveMatches: string[] = [];
        let readError: string | null = null;

        if (response && /(?:text\/|javascript|json|manifest|xml)/i.test(contentType)) {
          try {
            const body = await response.clone().text();
            sensitiveMatches = values.filter((value) => body.includes(value));
          } catch (error) {
            readError = error instanceof Error ? error.message : String(error);
          }
        }

        entries.push({
          cacheName,
          url: request.url,
          method: request.method,
          contentType,
          sensitiveMatches,
          readError,
        });
      }
    }

    return { cacheNames, entries };
  }, { values: sensitiveValues.filter(Boolean) });
}

test("manifest is installable in standalone mode with reachable start URL and icons", async ({ request }) => {
  const response = await request.get(MANIFEST_PATH);
  expect(response.ok(), `manifest request failed with HTTP ${response.status()}`).toBeTruthy();
  expect(response.headers()["content-type"] ?? "").toMatch(/application\/(?:manifest\+json|json)/i);

  const manifest = (await response.json()) as WebAppManifest;
  expect(manifest.name?.trim()).toBeTruthy();
  expect(manifest.short_name?.trim()).toBeTruthy();
  expect(manifest.display).toBe("standalone");
  expect(manifest.start_url?.trim()).toBeTruthy();

  const manifestUrl = new URL(response.url());
  const startUrl = new URL(manifest.start_url!, manifestUrl);
  expect(startUrl.origin).toBe(manifestUrl.origin);
  const startResponse = await request.get(startUrl.href);
  expect(startResponse.ok(), `manifest start_url failed with HTTP ${startResponse.status()}`).toBeTruthy();

  const icons = manifest.icons ?? [];
  const declaredSizes = new Set(icons.flatMap((icon) => (icon.sizes ?? "").split(/\s+/).filter(Boolean)));
  expect(declaredSizes).toContain("192x192");
  expect(declaredSizes).toContain("512x512");

  for (const icon of icons) {
    expect(icon.src?.trim()).toBeTruthy();
    const iconUrl = new URL(icon.src!, manifestUrl);
    expect(iconUrl.origin).toBe(manifestUrl.origin);
    const iconResponse = await request.get(iconUrl.href);
    expect(iconResponse.ok(), `manifest icon failed: ${iconUrl.pathname}`).toBeTruthy();
  }
});

test("first online calculation remains identical after an offline reload without persisting or uploading data", async ({
  context,
  page,
}, testInfo) => {
  test.setTimeout(180_000);

  const metrics: Partial<Record<MetricName, number>> = {};
  const observedRequests: ObservedRequest[] = [];
  page.on("request", (request) => {
    observedRequests.push({
      method: request.method(),
      resourceType: request.resourceType(),
      url: request.url(),
      postData: request.postData(),
    });
  });

  try {
    const firstLoadStarted = Date.now();
    await page.goto(APP_PATH, { waitUntil: "domcontentloaded" });
    await expect(MOBILE_E2E.appShell(page)).toBeVisible({ timeout: 15_000 });
    metrics.FIRST_LOAD_MS = Date.now() - firstLoadStarted;

    const firstInitStarted = Date.now();
    await expect(MOBILE_E2E.runtimeStatus(page)).toHaveAttribute("data-state", "ready", { timeout: 120_000 });
    await expect(MOBILE_E2E.offlineReady(page)).toHaveAttribute("data-state", "ready", { timeout: 30_000 });
    metrics.FIRST_INIT_MS = Date.now() - firstInitStarted;

    await expect
      .poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller)), {
        message: "the first successful online load must be controlled before going offline",
        timeout: 30_000,
      })
      .toBe(true);
    const serviceWorker = await page.evaluate(async () => {
      const registration = await navigator.serviceWorker.ready;
      return {
        active: Boolean(registration.active),
        scope: registration.scope,
        controlled: Boolean(navigator.serviceWorker.controller),
      };
    });
    expect(serviceWorker.active).toBe(true);
    expect(serviceWorker.controlled).toBe(true);
    expect(new URL(serviceWorker.scope).origin).toBe(new URL(page.url()).origin);

    await fillSyntheticInput(page);
    const firstCalcStarted = Date.now();
    const onlineResult = await calculateAndReadResult(page);
    metrics.FIRST_CALC_MS = Date.now() - firstCalcStarted;

    const onlineStorage = await storageAudit(page);
    expectNoPersistentUserData(onlineStorage);

    await context.setOffline(true);
    const secondLoadStarted = Date.now();
    await page.reload({ waitUntil: "domcontentloaded", timeout: 60_000 });
    await expect(MOBILE_E2E.appShell(page)).toBeVisible({ timeout: 15_000 });
    await expect(MOBILE_E2E.runtimeStatus(page)).toHaveAttribute("data-state", "ready", { timeout: 120_000 });
    metrics.SECOND_LOAD_MS = Date.now() - secondLoadStarted;

    await expect(MOBILE_E2E.birthDate(page)).toHaveValue("");
    await expect(MOBILE_E2E.birthTime(page)).toHaveValue("");
    await expect(MOBILE_E2E.locationNote(page)).toHaveValue("");
    await expect(MOBILE_E2E.longitude(page)).toHaveValue("");
    await expect(MOBILE_E2E.latitude(page)).toHaveValue("");
    await expect(MOBILE_E2E.trueSolarTime(page)).not.toBeChecked();

    await fillSyntheticInput(page);
    const secondCalcStarted = Date.now();
    const offlineResult = await calculateAndReadResult(page);
    metrics.SECOND_CALC_MS = Date.now() - secondCalcStarted;

    expect(offlineResult.canonicalResult).toEqual(onlineResult.canonicalResult);
    expect(offlineResult.hash).toBe(onlineResult.hash);

    const offlineStorage = await storageAudit(page);
    expectNoPersistentUserData(offlineStorage);

    const cacheAudit = await cacheStorageAudit(page, [SYNTHETIC_INPUT.locationNote, onlineResult.hash]);
    await attachJson(testInfo, "cache-storage-audit", cacheAudit);
    expect(cacheAudit.cacheNames.length).toBeGreaterThan(0);
    expect(cacheAudit.entries.length).toBeGreaterThan(0);

    const appOrigin = new URL(page.url()).origin;
    for (const entry of cacheAudit.entries) {
      const url = new URL(entry.url);
      expect(entry.method, `non-GET CacheStorage entry: ${entry.url}`).toBe("GET");
      expect(url.origin, `cross-origin CacheStorage entry: ${entry.url}`).toBe(appOrigin);
      expect(
        STATIC_CACHE_PATHS.some((pattern) => pattern.test(url.pathname)),
        `non-static CacheStorage entry: ${entry.url}`,
      ).toBe(true);
      expect(url.pathname, `API response cached: ${entry.url}`).not.toMatch(/^\/api(?:\/|$)/i);
      expect(entry.sensitiveMatches, `sensitive value cached: ${entry.url}`).toEqual([]);
      expect(entry.readError, `could not audit cached text response: ${entry.url}`).toBeNull();
    }

    const forbiddenMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);
    const mutationRequests = observedRequests.filter((request) => forbiddenMethods.has(request.method.toUpperCase()));
    const apiRequests = observedRequests.filter((request) => {
      const url = new URL(request.url);
      return /^\/api(?:\/|$)/i.test(url.pathname);
    });
    const externalHttpRequests = observedRequests.filter((request) => {
      const url = new URL(request.url);
      return ["http:", "https:"].includes(url.protocol) && url.origin !== appOrigin;
    });
    const serializedRequests = JSON.stringify(observedRequests);

    await attachJson(testInfo, "network-privacy-audit", observedRequests);
    await attachJson(testInfo, "storage-privacy-audit", { online: onlineStorage, offline: offlineStorage });
    expect(mutationRequests).toEqual([]);
    expect(apiRequests).toEqual([]);
    expect(externalHttpRequests).toEqual([]);
    expect(serializedRequests).not.toContain(SYNTHETIC_INPUT.locationNote);
  } finally {
    await context.setOffline(false).catch(() => undefined);
    await attachMetrics(testInfo, metrics);
  }
});
