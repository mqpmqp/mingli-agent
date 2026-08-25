import { readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

import {
  expect,
  test,
  type BrowserContext,
  type Locator,
  type Page,
  type Request,
  type TestInfo,
} from "@playwright/test";

type WebAppManifest = {
  name?: string;
  short_name?: string;
  start_url?: string;
  scope?: string;
  display?: string;
  orientation?: string;
  background_color?: string;
  theme_color?: string;
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
  query: Array<[string, string]>;
  allHeaders: Record<string, string>;
  postData: string | null;
};

type RuntimeManifest = {
  first_load_bytes: number;
  files: Array<{ path: string; bytes: number; sha256: string }>;
};

type RuntimeNetworkRecord = {
  url: string;
  path: string;
  method: string;
  resourceType: string;
  initiator: "page" | "service-worker";
  servedByServiceWorker: boolean;
  fromMemoryOrDiskCache: boolean;
  encodedBodyBytes: number;
  encodedTransferBytes: number;
  decodedBodyBytes: number;
  measurementError: string | null;
};

type ColdStartServerRecord = {
  path: string;
  method: string;
  encodedBodyBytes: number;
  encodedTransferBytes: number;
  decodedBodyBytes: number;
};

type ColdStartServer = {
  origin: string;
  records: ColdStartServerRecord[];
  close: () => Promise<void>;
};

const APP_PATH = "/";
const MANIFEST_PATH = "/manifest.webmanifest";
const DIST_ROOT = fileURLToPath(new URL("../dist/", import.meta.url));
const METRIC_NAMES: MetricName[] = [
  "FIRST_LOAD_MS",
  "FIRST_INIT_MS",
  "FIRST_CALC_MS",
  "SECOND_LOAD_MS",
  "SECOND_CALC_MS",
];

const SYNTHETIC_INPUT = {
  gender: "female",
  calendar: "lunar",
  birthDate: "2023-02-29",
  lunarYear: "2023",
  lunarMonth: "2",
  lunarDay: "29",
  birthTime: "13:27",
  timezone: "Pacific/Chatham",
  locationNote: "PW_ALL_FIELDS_SENTINEL_7f3a9c2e",
  longitude: "-176.54321",
  latitude: "-43.98765",
  trueSolarTime: true,
  isLeapMonth: true,
  fold: "0",
} as const;

const DISTINCTIVE_SENSITIVE_VALUES = [
  SYNTHETIC_INPUT.birthDate,
  SYNTHETIC_INPUT.birthTime,
  SYNTHETIC_INPUT.timezone,
  SYNTHETIC_INPUT.locationNote,
  SYNTHETIC_INPUT.longitude,
  SYNTHETIC_INPUT.latitude,
] as const;

const STRUCTURED_SENSITIVE_FIELDS = [
  { names: ["gender"], value: SYNTHETIC_INPUT.gender },
  { names: ["calendar"], value: SYNTHETIC_INPUT.calendar },
  { names: ["birth_date", "birthDate"], value: SYNTHETIC_INPUT.birthDate },
  { names: ["lunar_year", "lunarYear"], value: SYNTHETIC_INPUT.lunarYear },
  { names: ["lunar_month", "lunarMonth"], value: SYNTHETIC_INPUT.lunarMonth },
  { names: ["lunar_day", "lunarDay"], value: SYNTHETIC_INPUT.lunarDay },
  { names: ["birth_time", "birthTime"], value: SYNTHETIC_INPUT.birthTime },
  { names: ["timezone"], value: SYNTHETIC_INPUT.timezone },
  { names: ["longitude"], value: SYNTHETIC_INPUT.longitude },
  { names: ["latitude"], value: SYNTHETIC_INPUT.latitude },
  { names: ["is_leap_month", "isLeapMonth"], value: String(SYNTHETIC_INPUT.isLeapMonth) },
  { names: ["true_solar_time", "trueSolarTime"], value: String(SYNTHETIC_INPUT.trueSolarTime) },
  { names: ["fold"], value: SYNTHETIC_INPUT.fold },
  { names: ["birth_location_note", "birthLocationNote"], value: SYNTHETIC_INPUT.locationNote },
] as const;

// Stable mobile E2E contract. The app should expose state through the DOM rather
// than requiring tests to call its internal runtime or calculation objects.
const MOBILE_E2E = {
  appShell: (page: Page) => page.getByTestId("mingli-app"),
  runtimeStatus: (page: Page) => page.getByTestId("runtime-status"),
  offlineReady: (page: Page) => page.getByTestId("offline-ready"),
  genderMale: (page: Page) => page.getByTestId("gender-male"),
  genderFemale: (page: Page) => page.getByTestId("gender-female"),
  calendarSolar: (page: Page) => page.getByTestId("calendar-solar"),
  calendarLunar: (page: Page) => page.getByTestId("calendar-lunar"),
  birthDate: (page: Page) => page.getByTestId("birth-date"),
  lunarYear: (page: Page) => page.getByTestId("lunar-year"),
  lunarMonth: (page: Page) => page.getByTestId("lunar-month"),
  lunarDay: (page: Page) => page.getByTestId("lunar-day"),
  birthTime: (page: Page) => page.getByTestId("birth-time"),
  timezone: (page: Page) => page.getByTestId("timezone"),
  locationNote: (page: Page) => page.getByTestId("location-note"),
  longitude: (page: Page) => page.getByTestId("longitude"),
  latitude: (page: Page) => page.getByTestId("latitude"),
  trueSolarTime: (page: Page) => page.getByTestId("true-solar-time"),
  leapMonth: (page: Page) => page.getByTestId("leap-month"),
  fold: (page: Page) => page.locator('[name="fold"]'),
  coordinateConfirm: (page: Page) => page.getByTestId("coordinate-confirm"),
  calculate: (page: Page) => page.getByTestId("calculate"),
  result: (page: Page) => page.getByTestId("result"),
  resultJson: (page: Page) => page.getByTestId("result-json"),
  resultHash: (page: Page) => page.getByTestId("canonical-result-hash"),
  clearData: (page: Page) => page.getByTestId("clear-data"),
  formError: (page: Page) => page.getByTestId("form-error"),
  calculationError: (page: Page) => page.getByTestId("calculation-error"),
  actionFeedback: (page: Page) => page.getByTestId("action-feedback"),
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

async function readRuntimeManifest(): Promise<RuntimeManifest> {
  const raw = await readFile(new URL("../public/runtime/runtime-manifest.json", import.meta.url), "utf8");
  const value = JSON.parse(raw) as Partial<RuntimeManifest>;
  if (!Number.isSafeInteger(value.first_load_bytes) || value.first_load_bytes! <= 0 || !Array.isArray(value.files)) {
    throw new Error("runtime-manifest.json 缺少可测量的 first_load_bytes/files");
  }
  if (
    value.files.length === 0 ||
    !value.files.every(
      (file) =>
        typeof file?.path === "string" &&
        file.path !== "" &&
        Number.isSafeInteger(file.bytes) &&
        file.bytes > 0 &&
        /^[0-9a-f]{64}$/.test(file.sha256),
    )
  ) {
    throw new Error("runtime-manifest.json files 不能用于 cold-start 测量");
  }
  return value as RuntimeManifest;
}

async function measureRuntimeRequest(request: Request): Promise<RuntimeNetworkRecord> {
  const url = new URL(request.url());
  const base = {
    url: request.url(),
    path: url.pathname,
    method: request.method(),
    resourceType: request.resourceType(),
    initiator: request.serviceWorker() ? ("service-worker" as const) : ("page" as const),
  };

  try {
    const response = await request.response();
    if (!response) throw new Error("request finished without a response");
    const [sizes, body] = await Promise.all([request.sizes(), response.body()]);
    const servedByServiceWorker = response.fromServiceWorker();
    const fromMemoryOrDiskCache =
      !servedByServiceWorker && sizes.responseBodySize === 0 && sizes.responseHeadersSize === 0 && body.length > 0;
    return {
      ...base,
      servedByServiceWorker,
      fromMemoryOrDiskCache,
      encodedBodyBytes: sizes.responseBodySize,
      encodedTransferBytes: sizes.responseBodySize + sizes.responseHeadersSize,
      decodedBodyBytes: body.length,
      measurementError: null,
    };
  } catch (error) {
    return {
      ...base,
      servedByServiceWorker: false,
      fromMemoryOrDiskCache: false,
      encodedBodyBytes: 0,
      encodedTransferBytes: 0,
      decodedBodyBytes: 0,
      measurementError: error instanceof Error ? error.message : String(error),
    };
  }
}

async function captureObservedRequest(request: Request): Promise<ObservedRequest> {
  const url = new URL(request.url());
  return {
    method: request.method(),
    resourceType: request.resourceType(),
    url: request.url(),
    query: [...url.searchParams.entries()],
    allHeaders: await request.allHeaders(),
    postData: request.postData(),
  };
}

function normalizeFieldName(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function sensitiveRequestLeaks(requests: ObservedRequest[]): string[] {
  const leaks: string[] = [];
  for (const request of requests) {
    const headersText = JSON.stringify(request.allHeaders);
    const postData = request.postData ?? "";
    for (const value of DISTINCTIVE_SENSITIVE_VALUES) {
      if (
        request.url.includes(value) ||
        request.url.includes(encodeURIComponent(value)) ||
        headersText.includes(value) ||
        postData.includes(value)
      ) {
        leaks.push(`${request.method} ${new URL(request.url).pathname}: distinctive value ${value}`);
      }
    }

    for (const field of STRUCTURED_SENSITIVE_FIELDS) {
      const normalizedNames = new Set(field.names.map(normalizeFieldName));
      const expectedValue = field.value.toLowerCase();
      for (const [name, value] of request.query) {
        if (normalizedNames.has(normalizeFieldName(name)) && value.toLowerCase().includes(expectedValue)) {
          leaks.push(`${request.method} ${new URL(request.url).pathname}: query field ${name}`);
        }
      }
      for (const [name, value] of Object.entries(request.allHeaders)) {
        if (normalizedNames.has(normalizeFieldName(name)) && value.toLowerCase().includes(expectedValue)) {
          leaks.push(`${request.method} ${new URL(request.url).pathname}: header field ${name}`);
        }
      }
      const normalizedPostData = postData.toLowerCase();
      for (const name of field.names.map((value) => value.toLowerCase())) {
        const patterns = [
          `"${name}":"${expectedValue}"`,
          `"${name}":${expectedValue}`,
          `${name}=${expectedValue}`,
          `${name}:${expectedValue}`,
          `${encodeURIComponent(name)}=${encodeURIComponent(field.value)}`.toLowerCase(),
        ];
        if (patterns.some((pattern) => normalizedPostData.includes(pattern))) {
          leaks.push(`${request.method} ${new URL(request.url).pathname}: body field ${name}`);
        }
      }
    }
  }
  return [...new Set(leaks)].sort();
}

function pngDimensions(body: Buffer): { width: number; height: number } {
  const signature = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  expect(body.subarray(0, signature.length), "icon is missing the PNG signature").toEqual(signature);
  expect(body.subarray(12, 16).toString("ascii"), "PNG first chunk must be IHDR").toBe("IHDR");
  return { width: body.readUInt32BE(16), height: body.readUInt32BE(20) };
}

function contentTypeForPath(path: string): string {
  const contentTypes: Record<string, string> = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".wasm": "application/wasm",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".whl": "application/octet-stream",
    ".zip": "application/zip",
  };
  return contentTypes[extname(path).toLowerCase()] ?? "application/octet-stream";
}

async function startColdStartServer(): Promise<ColdStartServer> {
  const records: ColdStartServerRecord[] = [];
  const distPrefix = DIST_ROOT.endsWith(sep) ? DIST_ROOT : DIST_ROOT + sep;
  const server = createServer((request, response) => {
    void (async () => {
      const requestUrl = new URL(request.url ?? "/", "http://127.0.0.1");
      const decodedPath = decodeURIComponent(requestUrl.pathname);
      const relativePath = decodedPath === "/" ? "index.html" : decodedPath.slice(1);
      const absolutePath = resolve(DIST_ROOT, relativePath);
      const method = request.method ?? "GET";

      let statusCode = 200;
      let body: Buffer;
      if (method !== "GET" && method !== "HEAD") {
        statusCode = 405;
        body = Buffer.from("method not allowed", "utf8");
      } else if (decodedPath === "/__mingli-cold-start-probe__") {
        body = Buffer.from("<!doctype html><title>cold-start-probe</title>", "utf8");
      } else if (!absolutePath.startsWith(distPrefix)) {
        statusCode = 403;
        body = Buffer.from("forbidden", "utf8");
      } else {
        try {
          body = await readFile(absolutePath);
        } catch {
          statusCode = 404;
          body = Buffer.from("not found", "utf8");
        }
      }

      response.statusCode = statusCode;
      response.setHeader(
        "Content-Type",
        decodedPath === "/__mingli-cold-start-probe__" ? "text/html; charset=utf-8" : contentTypeForPath(relativePath),
      );
      response.setHeader("Content-Length", String(method === "HEAD" ? 0 : body.length));
      response.setHeader("Cache-Control", "no-store");
      response.setHeader("Connection", "close");

      const socket = response.socket;
      const bytesBefore = socket?.bytesWritten ?? 0;
      response.once("finish", () => {
        if (!decodedPath.startsWith("/runtime/")) return;
        const encodedTransferBytes = socket ? socket.bytesWritten - bytesBefore : body.length;
        records.push({
          path: decodedPath,
          method,
          encodedBodyBytes: method === "HEAD" ? 0 : body.length,
          encodedTransferBytes,
          decodedBodyBytes: method === "HEAD" ? 0 : body.length,
        });
      });
      response.end(method === "HEAD" ? undefined : body);
    })().catch(() => {
      if (!response.headersSent) {
        response.statusCode = 500;
        response.setHeader("Content-Type", "text/plain; charset=utf-8");
      }
      response.end("cold-start server error");
    });
  });

  await new Promise<void>((resolveListen, rejectListen) => {
    const onError = (error: Error): void => rejectListen(error);
    server.once("error", onError);
    server.listen(0, "127.0.0.1", () => {
      server.off("error", onError);
      resolveListen();
    });
  });
  const address = server.address() as AddressInfo;
  return {
    origin: `http://127.0.0.1:${address.port}`,
    records,
    close: () =>
      new Promise<void>((resolveClose, rejectClose) => {
        server.close((error) => {
          if (error) rejectClose(error);
          else resolveClose();
        });
      }),
  };
}

function correlateColdStartRecords(
  serverRecords: ColdStartServerRecord[],
  pageRecords: RuntimeNetworkRecord[],
  origin: string,
): RuntimeNetworkRecord[] {
  const directPageRecords = new Map<string, RuntimeNetworkRecord[]>();
  const nonNetworkPageRecords: RuntimeNetworkRecord[] = [];

  for (const record of pageRecords) {
    const isDirectNetwork =
      record.measurementError === null &&
      record.encodedBodyBytes > 0 &&
      !record.fromMemoryOrDiskCache &&
      !record.servedByServiceWorker;
    if (!isDirectNetwork) {
      nonNetworkPageRecords.push(record);
      continue;
    }
    const matches = directPageRecords.get(record.path) ?? [];
    matches.push(record);
    directPageRecords.set(record.path, matches);
  }

  const correlated = serverRecords.map((record): RuntimeNetworkRecord => {
    const pageMatches = directPageRecords.get(record.path) ?? [];
    const pageMatch = pageMatches.shift();
    directPageRecords.set(record.path, pageMatches);
    return {
      url: origin + record.path,
      path: record.path,
      method: record.method,
      resourceType: pageMatch?.resourceType ?? "fetch",
      initiator: pageMatch ? "page" : "service-worker",
      servedByServiceWorker: false,
      fromMemoryOrDiskCache: false,
      encodedBodyBytes: record.encodedBodyBytes,
      encodedTransferBytes: record.encodedTransferBytes,
      decodedBodyBytes: record.decodedBodyBytes,
      measurementError:
        record.encodedTransferBytes >= record.encodedBodyBytes
          ? null
          : "server transfer receipt was smaller than the encoded response body",
    };
  });

  for (const unmatched of directPageRecords.values()) {
    for (const record of unmatched) {
      correlated.push({
        ...record,
        measurementError: "page network request was missing from the isolated server receipt",
      });
    }
  }
  return [...correlated, ...nonNetworkPageRecords];
}
async function assertEmptyColdStartState(context: BrowserContext, page: Page, origin: string): Promise<void> {
  expect(context.serviceWorkers(), "fresh Chromium context already has a Service Worker").toHaveLength(0);
  await page.route(`${origin}/__mingli-cold-start-probe__`, async (route) => {
    await route.fulfill({ status: 200, contentType: "text/html", body: "<!doctype html><title>cold-start-probe</title>" });
  });
  await page.goto(`${origin}/__mingli-cold-start-probe__`, { waitUntil: "domcontentloaded" });
  expect(await page.evaluate(async () => caches.keys()), "fresh Chromium context already has CacheStorage data").toEqual([]);
  await page.unroute(`${origin}/__mingli-cold-start-probe__`);
}

async function fillSyntheticInput(page: Page): Promise<void> {
  await MOBILE_E2E.genderFemale(page).check({ force: true });
  await MOBILE_E2E.calendarLunar(page).check({ force: true });
  await expect(MOBILE_E2E.genderFemale(page)).toBeChecked();
  await expect(MOBILE_E2E.calendarLunar(page)).toBeChecked();
  await expect(MOBILE_E2E.birthDate(page)).toBeHidden();
  await MOBILE_E2E.lunarYear(page).fill(SYNTHETIC_INPUT.lunarYear);
  await MOBILE_E2E.lunarMonth(page).fill(SYNTHETIC_INPUT.lunarMonth);
  await MOBILE_E2E.lunarDay(page).fill(SYNTHETIC_INPUT.lunarDay);
  await MOBILE_E2E.birthTime(page).fill(SYNTHETIC_INPUT.birthTime);
  await MOBILE_E2E.timezone(page).fill(SYNTHETIC_INPUT.timezone);
  await MOBILE_E2E.locationNote(page).fill(SYNTHETIC_INPUT.locationNote);
  await MOBILE_E2E.longitude(page).fill(SYNTHETIC_INPUT.longitude);
  await MOBILE_E2E.latitude(page).fill(SYNTHETIC_INPUT.latitude);
  await MOBILE_E2E.trueSolarTime(page).check({ force: true });
  await MOBILE_E2E.leapMonth(page).check({ force: true });
  if (!(await MOBILE_E2E.fold(page).isVisible())) {
    await page.locator("details.advanced-options > summary").click();
  }
  await MOBILE_E2E.fold(page).selectOption(SYNTHETIC_INPUT.fold);
  await MOBILE_E2E.coordinateConfirm(page).check({ force: true });
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
      bodyBytes: number;
      bodySha256: string | null;
      sensitiveMatches: string[];
      readError: string | null;
    }> = [];

    for (const cacheName of cacheNames) {
      const cache = await caches.open(cacheName);
      for (const request of await cache.keys()) {
        const response = await cache.match(request);
        const contentType = response?.headers.get("content-type") ?? "";
        let bodyBytes = 0;
        let bodySha256: string | null = null;
        let sensitiveMatches: string[] = [];
        let readError: string | null = null;

        if (response) {
          try {
            const bytes = new Uint8Array(await response.clone().arrayBuffer());
            bodyBytes = bytes.byteLength;
            const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
            bodySha256 = Array.from(digest, (byte) => byte.toString(16).padStart(2, "0")).join("");
            if (/(?:text\/|javascript|json|manifest|xml)/i.test(contentType)) {
              const body = new TextDecoder().decode(bytes);
              sensitiveMatches = values.filter((value) => body.includes(value));
            }
          } catch (error) {
            readError = error instanceof Error ? error.message : String(error);
          }
        }

        entries.push({
          cacheName,
          url: request.url,
          method: request.method,
          contentType,
          bodyBytes,
          bodySha256,
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
  expect(manifest.start_url).toBe("./");
  expect(manifest.scope).toBe("./");
  expect(manifest.display).toBe("standalone");
  expect(manifest.orientation).toBe("portrait-primary");
  expect(manifest.background_color).toMatch(/^#[0-9a-f]{6}$/i);
  expect(manifest.theme_color).toMatch(/^#[0-9a-f]{6}$/i);

  const manifestUrl = new URL(response.url());
  const startUrl = new URL(manifest.start_url!, manifestUrl);
  const scopeUrl = new URL(manifest.scope!, manifestUrl);
  expect(startUrl.origin).toBe(manifestUrl.origin);
  expect(scopeUrl.origin).toBe(manifestUrl.origin);
  expect(startUrl.href.startsWith(scopeUrl.href), "manifest start_url must remain inside scope").toBe(true);
  const startResponse = await request.get(startUrl.href);
  expect(startResponse.ok(), `manifest start_url failed with HTTP ${startResponse.status()}`).toBeTruthy();

  const icons = manifest.icons ?? [];
  const declaredSizes = new Set(icons.flatMap((icon) => (icon.sizes ?? "").split(/\s+/).filter(Boolean)));
  expect(declaredSizes).toContain("192x192");
  expect(declaredSizes).toContain("512x512");

  for (const icon of icons) {
    expect(icon.src?.trim()).toBeTruthy();
    expect(icon.type).toBe("image/png");
    const sizes = (icon.sizes ?? "").split(/\s+/).filter(Boolean);
    expect(sizes, `manifest icon must declare one exact size: ${icon.src}`).toHaveLength(1);
    const sizeMatch = /^(\d+)x(\d+)$/.exec(sizes[0]!);
    expect(sizeMatch, `invalid manifest icon size: ${icon.sizes}`).not.toBeNull();
    const iconUrl = new URL(icon.src!, manifestUrl);
    expect(iconUrl.origin).toBe(manifestUrl.origin);
    const iconResponse = await request.get(iconUrl.href);
    expect(iconResponse.ok(), `manifest icon failed: ${iconUrl.pathname}`).toBeTruthy();
    expect(iconResponse.headers()["content-type"] ?? "").toMatch(/^image\/png(?:;|$)/i);
    expect(pngDimensions(await iconResponse.body())).toEqual({
      width: Number(sizeMatch![1]),
      height: Number(sizeMatch![2]),
    });
    if (sizes[0] === "512x512") expect(icon.purpose?.split(/\s+/)).toContain("maskable");
  }

  const appHtml = await startResponse.text();
  const appleLink = appHtml.match(/<link\b[^>]*\brel=["']apple-touch-icon["'][^>]*>/i)?.[0] ?? "";
  const appleHref = appleLink.match(/\bhref=["']([^"']+)["']/i)?.[1] ?? "";
  expect(appleHref, "document must declare an apple-touch-icon").not.toBe("");
  const appleResponse = await request.get(new URL(appleHref, startUrl).href);
  expect(appleResponse.ok()).toBe(true);
  expect(appleResponse.headers()["content-type"] ?? "").toMatch(/^image\/png(?:;|$)/i);
  expect(pngDimensions(await appleResponse.body())).toEqual({ width: 180, height: 180 });
});

test("Chromium accepts the processed PWA manifest without installability errors", async ({ context, page }, testInfo) => {
  test.setTimeout(120_000);
  await page.goto(APP_PATH, { waitUntil: "domcontentloaded" });
  await expect(MOBILE_E2E.offlineReady(page)).toHaveAttribute("data-state", "ready", { timeout: 60_000 });

  const cdp = await context.newCDPSession(page);
  try {
    const appManifest = await cdp.send("Page.getAppManifest");
    const installability = await cdp.send("Page.getInstallabilityErrors");
    await attachJson(testInfo, "chromium-pwa-acceptance", { appManifest, installability });
    expect(appManifest.url).toMatch(/\/manifest\.webmanifest$/);
    expect(appManifest.errors).toEqual([]);
    expect(installability.installabilityErrors).toEqual([]);
    console.log("PWA_MANIFEST_INSTALLABILITY=PASS");
    console.log("CHROMIUM_PWA_ACCEPTANCE=PASS");
    console.log("IOS_PHYSICAL_INSTALL=NOT_RUN");
    console.log("ANDROID_PHYSICAL_INSTALL=NOT_RUN");
  } finally {
    await cdp.detach().catch(() => undefined);
  }
});

test("cold start transfers every fixed runtime asset over the network at most once", async ({ context, page }, testInfo) => {
  test.setTimeout(180_000);

  const coldStartServer = await startColdStartServer();
  const origin = coldStartServer.origin;
  const runtimeManifest = await readRuntimeManifest();
  const fixedAssetPaths = new Set(runtimeManifest.files.map((file) => `/runtime/${file.path}`));
  const monitoredRuntimePaths = new Set([...fixedAssetPaths, "/runtime/runtime-manifest.json"]);
  const measurements: Array<Promise<RuntimeNetworkRecord>> = [];
  const recordFinishedRequest = (request: Request): void => {
    if (!request.serviceWorker() && new URL(request.url()).pathname.startsWith("/runtime/")) {
      measurements.push(measureRuntimeRequest(request));
    }
  };

  await assertEmptyColdStartState(context, page, origin);
  const cdp = await context.newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Storage.clearDataForOrigin", { origin, storageTypes: "all" });
  await cdp.send("Network.clearBrowserCache");
  const browserVersion = await cdp.send("Browser.getVersion");
  context.on("requestfinished", recordFinishedRequest);

  try {
    await page.goto(`${origin}${APP_PATH}`, { waitUntil: "domcontentloaded" });
    await expect(MOBILE_E2E.runtimeStatus(page)).toHaveAttribute("data-state", "ready", { timeout: 120_000 });
    await expect(MOBILE_E2E.offlineReady(page)).toHaveAttribute("data-state", "ready", { timeout: 60_000 });
    await expect
      .poll(() => {
        const serverPaths = new Set(coldStartServer.records.map((record) => record.path));
        return [...monitoredRuntimePaths].filter((path) => !serverPaths.has(path));
      }, {
        message: "isolated server did not receive every cold-start runtime asset request",
        timeout: 30_000,
      })
      .toEqual([]);

    const records = correlateColdStartRecords(
      coldStartServer.records,
      await Promise.all(measurements),
      origin,
    ).filter((record) => monitoredRuntimePaths.has(record.path));
    const errors = records.filter((record) => record.measurementError !== null);
    const observedPaths = new Set(records.map((record) => record.path));
    const missingFixedAssets = [...monitoredRuntimePaths].filter((path) => !observedPaths.has(path));
    const realNetworkTransfers = records.filter(
      (record) =>
        record.encodedBodyBytes > 0 && !record.fromMemoryOrDiskCache && !record.servedByServiceWorker,
    );
    const transfersByPath = new Map<string, RuntimeNetworkRecord[]>();
    for (const record of realNetworkTransfers) {
      const transfers = transfersByPath.get(record.path) ?? [];
      transfers.push(record);
      transfersByPath.set(record.path, transfers);
    }
    const duplicatePaths = [...transfersByPath.entries()]
      .filter(([, transfers]) => transfers.length > 1)
      .map(([path, transfers]) => ({
        path,
        networkTransfers: transfers.length,
        extraTransfers: transfers.length - 1,
        initiators: transfers.map((record) => record.initiator),
        encodedBodyBytes: transfers.map((record) => record.encodedBodyBytes),
      }));
    const duplicateRuntimeNetworkFetches = duplicatePaths.reduce(
      (total, duplicate) => total + duplicate.extraTransfers,
      0,
    );
    const firstLoadTransferBytes = realNetworkTransfers.reduce(
      (total, record) => total + record.encodedTransferBytes,
      0,
    );
    const environment = [
      "fresh Playwright Chromium context",
      "no pre-existing Service Worker",
      "no pre-existing CacheStorage",
      "CDP Storage.clearDataForOrigin(all)",
      "CDP Network.clearBrowserCache",
      "isolated loopback static server with Cache-Control: no-store",
      "server socket byte receipts correlated with page requests; remainder attributed to Service Worker install",
      browserVersion.product,
      origin,
    ].join("; ");
    const report = {
      FIRST_LOAD_ASSET_BYTES: runtimeManifest.first_load_bytes,
      FIRST_LOAD_TRANSFER_BYTES: firstLoadTransferBytes,
      DUPLICATE_RUNTIME_NETWORK_FETCHES: duplicateRuntimeNetworkFetches,
      COLD_START_MEASUREMENT_ENVIRONMENT: environment,
      fixedAssetCount: runtimeManifest.files.length,
      observedRuntimeRequestCount: records.length,
      realNetworkTransferCount: realNetworkTransfers.length,
      missingFixedAssets,
      duplicatePaths,
      records,
    };

    console.log(`FIRST_LOAD_ASSET_BYTES=${report.FIRST_LOAD_ASSET_BYTES}`);
    console.log(`FIRST_LOAD_TRANSFER_BYTES=${report.FIRST_LOAD_TRANSFER_BYTES}`);
    console.log(`DUPLICATE_RUNTIME_NETWORK_FETCHES=${report.DUPLICATE_RUNTIME_NETWORK_FETCHES}`);
    console.log(`COLD_START_MEASUREMENT_ENVIRONMENT=${report.COLD_START_MEASUREMENT_ENVIRONMENT}`);
    await attachJson(testInfo, "cold-start-runtime-network", report);

    expect(errors, `cold-start measurement failed: ${JSON.stringify(errors)}`).toEqual([]);
    expect(missingFixedAssets, `fixed runtime assets not observed: ${missingFixedAssets.join(", ")}`).toEqual([]);
    expect(
      duplicateRuntimeNetworkFetches,
      `duplicate real runtime transfers: ${JSON.stringify(duplicatePaths)}`,
    ).toBe(0);
  } finally {
    context.off("requestfinished", recordFinishedRequest);
    await cdp.detach().catch(() => undefined);
    await coldStartServer.close();
  }
});

test("all-field privacy sentinels stay local and online/offline results remain identical", async ({
  context,
  page,
}, testInfo) => {
  test.setTimeout(180_000);

  const metrics: Partial<Record<MetricName, number>> = {};
  const observedRequestReceipts: Array<Promise<ObservedRequest>> = [];
  page.on("request", (request) => {
    observedRequestReceipts.push(captureObservedRequest(request));
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

    expect(
      await page.evaluate(() => Boolean(navigator.serviceWorker.controller)),
      "offline-ready must only be shown after the first page is controlled",
    ).toBe(true);
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
    const baselineCacheAudit = await cacheStorageAudit(page, [...DISTINCTIVE_SENSITIVE_VALUES]);
    expect(baselineCacheAudit.cacheNames.length).toBeGreaterThan(0);
    expect(baselineCacheAudit.entries.length).toBeGreaterThan(0);

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
    await expect(MOBILE_E2E.lunarYear(page)).toHaveValue("");
    await expect(MOBILE_E2E.lunarMonth(page)).toHaveValue("");
    await expect(MOBILE_E2E.lunarDay(page)).toHaveValue("");
    await expect(MOBILE_E2E.birthTime(page)).toHaveValue("");
    await expect(MOBILE_E2E.locationNote(page)).toHaveValue("");
    await expect(MOBILE_E2E.longitude(page)).toHaveValue("");
    await expect(MOBILE_E2E.latitude(page)).toHaveValue("");
    await expect(MOBILE_E2E.trueSolarTime(page)).not.toBeChecked();
    await expect(MOBILE_E2E.leapMonth(page)).not.toBeChecked();

    await fillSyntheticInput(page);
    const secondCalcStarted = Date.now();
    const offlineResult = await calculateAndReadResult(page);
    metrics.SECOND_CALC_MS = Date.now() - secondCalcStarted;

    expect(offlineResult.canonicalResult).toEqual(onlineResult.canonicalResult);
    expect(offlineResult.hash).toBe(onlineResult.hash);

    const offlineStorage = await storageAudit(page);
    expectNoPersistentUserData(offlineStorage);

    const cacheAudit = await cacheStorageAudit(page, [...DISTINCTIVE_SENSITIVE_VALUES, onlineResult.hash]);
    await attachJson(testInfo, "cache-storage-audit", { beforeInput: baselineCacheAudit, afterCalculation: cacheAudit });
    expect(cacheAudit.cacheNames.length).toBeGreaterThan(0);
    expect(cacheAudit.entries.length).toBeGreaterThan(0);

    const appOrigin = new URL(page.url()).origin;
    const baselineEntries = new Map(
      baselineCacheAudit.entries.map((entry) => [`${entry.cacheName}\n${entry.url}`, entry]),
    );
    for (const entry of cacheAudit.entries) {
      const url = new URL(entry.url);
      const baselineEntry = baselineEntries.get(`${entry.cacheName}\n${entry.url}`);
      expect(entry.method, `non-GET CacheStorage entry: ${entry.url}`).toBe("GET");
      expect(url.origin, `cross-origin CacheStorage entry: ${entry.url}`).toBe(appOrigin);
      expect(
        STATIC_CACHE_PATHS.some((pattern) => pattern.test(url.pathname)),
        `non-static CacheStorage entry: ${entry.url}`,
      ).toBe(true);
      expect(url.pathname, `API response cached: ${entry.url}`).not.toMatch(/^\/api(?:\/|$)/i);
      expect(baselineEntry, `new CacheStorage entry appeared after user input: ${entry.url}`).toBeDefined();
      expect(entry.bodyBytes, `cached response bytes changed after user input: ${entry.url}`).toBe(
        baselineEntry?.bodyBytes,
      );
      expect(entry.bodySha256, `cached response digest changed after user input: ${entry.url}`).toBe(
        baselineEntry?.bodySha256,
      );
      const baselineMatches = new Set(baselineEntry?.sensitiveMatches ?? []);
      expect(
        entry.sensitiveMatches.filter((value) => !baselineMatches.has(value)),
        `new sensitive value appeared in CacheStorage after user input: ${entry.url}`,
      ).toEqual([]);
      expect(entry.readError, `could not audit cached text response: ${entry.url}`).toBeNull();
    }

    await MOBILE_E2E.clearData(page).click();
    await expect(MOBILE_E2E.result(page)).toBeHidden();
    await expect(MOBILE_E2E.genderMale(page)).toBeChecked();
    await expect(MOBILE_E2E.calendarSolar(page)).toBeChecked();
    await expect(MOBILE_E2E.birthDate(page)).toBeVisible();
    await expect(MOBILE_E2E.birthDate(page)).toHaveValue("");
    await expect(MOBILE_E2E.lunarYear(page)).toHaveValue("");
    await expect(MOBILE_E2E.lunarMonth(page)).toHaveValue("");
    await expect(MOBILE_E2E.lunarDay(page)).toHaveValue("");
    await expect(MOBILE_E2E.birthTime(page)).toHaveValue("");
    await expect(MOBILE_E2E.timezone(page)).toHaveValue("Asia/Shanghai");
    await expect(MOBILE_E2E.locationNote(page)).toHaveValue("");
    await expect(MOBILE_E2E.longitude(page)).toHaveValue("");
    await expect(MOBILE_E2E.latitude(page)).toHaveValue("");
    await expect(MOBILE_E2E.trueSolarTime(page)).not.toBeChecked();
    await expect(MOBILE_E2E.leapMonth(page)).not.toBeChecked();
    await expect(MOBILE_E2E.coordinateConfirm(page)).not.toBeChecked();
    await expect(MOBILE_E2E.fold(page)).toHaveValue("0");
    await expect(MOBILE_E2E.formError(page)).toBeHidden();
    await expect(MOBILE_E2E.formError(page)).toHaveText("");
    await expect(MOBILE_E2E.calculationError(page)).toBeHidden();
    await expect(MOBILE_E2E.calculationError(page)).toHaveText("");
    await expect(MOBILE_E2E.resultJson(page)).toHaveValue("");
    await expect(MOBILE_E2E.actionFeedback(page)).toHaveText("");

    const domSensitiveMatches = await page.evaluate((values) => {
      const formValues = [...document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(
        "input, textarea, select",
      )].map((element) => element.value);
      const surfaces = [
        document.body.innerText,
        ...formValues,
        document.querySelector<HTMLElement>('[data-testid="action-feedback"]')?.innerText ?? "",
        document.querySelector<HTMLTextAreaElement>('[data-testid="result-json"]')?.value ?? "",
      ];
      return values.filter((value) => surfaces.some((surface) => surface.includes(value)));
    }, [...DISTINCTIVE_SENSITIVE_VALUES]);
    expect(domSensitiveMatches).toEqual([]);

    const observedRequests = await Promise.all(observedRequestReceipts);
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
    const analyticsRequests = observedRequests.filter((request) =>
      /(?:analytics|telemetry|tracking|doubleclick|google-analytics|\/collect(?:\/|\?|$))/i.test(request.url),
    );
    const privacyLeaks = sensitiveRequestLeaks(observedRequests);

    await attachJson(testInfo, "network-privacy-audit", observedRequests);
    await attachJson(testInfo, "storage-privacy-audit", {
      online: onlineStorage,
      offline: offlineStorage,
      domSensitiveMatches,
    });
    expect(mutationRequests).toEqual([]);
    expect(apiRequests).toEqual([]);
    expect(externalHttpRequests).toEqual([]);
    expect(analyticsRequests).toEqual([]);
    expect(privacyLeaks).toEqual([]);
  } finally {
    await context.setOffline(false).catch(() => undefined);
    await attachMetrics(testInfo, metrics);
  }
});

test("activating the current build removes older static cache generations", async ({ page, request }) => {
  test.setTimeout(120_000);
  const cachePrefix = "mingli-pwa-static-";
  const obsoleteCache = `${cachePrefix}obsolete-e2e-generation`;

  await page.goto(APP_PATH, { waitUntil: "domcontentloaded" });
  await expect(MOBILE_E2E.offlineReady(page)).toHaveAttribute("data-state", "ready", { timeout: 30_000 });
  const currentCaches = await page.evaluate(async (prefix) =>
    (await caches.keys()).filter((name) => name.startsWith(prefix)).sort(),
  cachePrefix);
  expect(currentCaches).toHaveLength(1);

  await page.evaluate(async ({ cacheName }) => {
    const cache = await caches.open(cacheName);
    await cache.put("/__obsolete-cache-sentinel", new Response("obsolete"));
  }, { cacheName: obsoleteCache });
  await expect.poll(() => page.evaluate(async (name) => (await caches.keys()).includes(name), obsoleteCache)).toBe(true);

  const workerResponse = await request.get("/sw.js");
  expect(workerResponse.ok()).toBe(true);
  const workerSource = `${await workerResponse.text()}\n// e2e generation two\n`;
  const workerPath = new URL("../dist/sw-generation-two.js", import.meta.url);
  await writeFile(workerPath, workerSource, "utf8");
  try {

  await page.evaluate(async () => {
    const registration = await navigator.serviceWorker.register("/sw-generation-two.js", { scope: "/" });
    const installing = registration.installing ?? registration.waiting;
    if (!installing) throw new Error("updated service worker did not enter installing or waiting");

    if (installing.state !== "installed") {
      await new Promise<void>((resolve, reject) => {
        const timeout = window.setTimeout(() => reject(new Error("updated service worker install timed out")), 30_000);
        installing.addEventListener("statechange", () => {
          if (installing.state === "installed") {
            window.clearTimeout(timeout);
            resolve();
          } else if (installing.state === "redundant") {
            window.clearTimeout(timeout);
            reject(new Error("updated service worker became redundant"));
          }
        });
      });
    }

    const waiting = registration.waiting;
    if (!waiting) throw new Error("updated service worker did not reach waiting");
    const controllerChanged = new Promise<void>((resolve, reject) => {
      const timeout = window.setTimeout(() => reject(new Error("controllerchange timed out")), 30_000);
      navigator.serviceWorker.addEventListener(
        "controllerchange",
        () => {
          window.clearTimeout(timeout);
          resolve();
        },
        { once: true },
      );
    });
    waiting.postMessage({ type: "SKIP_WAITING" });
    await controllerChanged;
  });

  await expect
    .poll(
      () => page.evaluate(async (prefix) => (await caches.keys()).filter((name) => name.startsWith(prefix)).sort(), cachePrefix),
      { timeout: 30_000 },
    )
    .toEqual(currentCaches);
  } finally {
    await rm(workerPath, { force: true });
  }
});
