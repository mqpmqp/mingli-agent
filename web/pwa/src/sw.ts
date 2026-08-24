type VersionBinding = {
  appBuildId: string;
  gitSha: string;
  wheelSha256: string;
  pyodideVersion: string;
  tzdataVersion: string;
};

type PwaAssetManifest = {
  schemaVersion: "mingli-pwa-assets@1.0";
  appBinding: VersionBinding;
  assets: string[];
};

declare const __MINGLI_BUILD_INFO__: VersionBinding;

const worker = self as unknown as ServiceWorkerGlobalScope;
const BUILD_INFO = Object.freeze({ ...__MINGLI_BUILD_INFO__ });
const CACHE_PREFIX = "mingli-pwa-static-";
const CACHE_NAME = CACHE_PREFIX + BUILD_INFO.appBuildId;
const ASSET_MANIFEST_PATH = "pwa-assets.json";
const VERSION_KEYS = [
  "appBuildId",
  "gitSha",
  "wheelSha256",
  "pyodideVersion",
  "tzdataVersion",
] as const satisfies readonly (keyof VersionBinding)[];

function isVersionBinding(value: unknown): value is VersionBinding {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return VERSION_KEYS.every((key) => typeof candidate[key] === "string" && candidate[key] !== "");
}

function matchesCurrentBuild(value: unknown): value is VersionBinding {
  return isVersionBinding(value) && VERSION_KEYS.every((key) => value[key] === BUILD_INFO[key]);
}

function isApiUrl(url: URL): boolean {
  const scopePath = new URL(worker.registration.scope).pathname;
  const relativePath = url.pathname.startsWith(scopePath) ? url.pathname.slice(scopePath.length) : url.pathname;
  return /^api(?:\/|$)/iu.test(relativePath);
}

function requestForStaticAsset(path: string): Request {
  if (
    path === "" ||
    path.startsWith("/") ||
    path.startsWith("\\") ||
    path.includes("\\") ||
    path.includes("?") ||
    path.includes("#")
  ) {
    throw new Error("静态缓存清单包含非 scope-relative 路径: " + path);
  }

  const url = new URL(path, worker.registration.scope);
  if (
    url.origin !== worker.location.origin ||
    !url.href.startsWith(worker.registration.scope) ||
    isApiUrl(url)
  ) {
    throw new Error("静态缓存清单包含越界或 API 路径: " + path);
  }

  return new Request(url, {
    method: "GET",
    cache: "reload",
    credentials: "same-origin",
  });
}

async function loadAssetManifest(): Promise<PwaAssetManifest> {
  const manifestUrl = new URL(ASSET_MANIFEST_PATH, worker.registration.scope);
  const response = await fetch(
    new Request(manifestUrl, {
      method: "GET",
      cache: "no-store",
      credentials: "same-origin",
    }),
  );
  if (!response.ok) {
    throw new Error("无法读取 PWA 静态缓存清单: HTTP " + response.status);
  }

  const value = (await response.json()) as Partial<PwaAssetManifest>;
  if (value.schemaVersion !== "mingli-pwa-assets@1.0") {
    throw new Error("PWA 静态缓存清单 schema 不受支持");
  }
  if (!matchesCurrentBuild(value.appBinding)) {
    throw new Error("PWA 静态缓存清单与当前应用版本不一致");
  }
  if (!Array.isArray(value.assets) || value.assets.length === 0) {
    throw new Error("PWA 静态缓存清单没有可缓存资源");
  }
  if (!value.assets.every((asset): asset is string => typeof asset === "string")) {
    throw new Error("PWA 静态缓存清单包含非字符串路径");
  }

  return value as PwaAssetManifest;
}

async function installStaticAssets(): Promise<void> {
  const manifest = await loadAssetManifest();
  const requests = manifest.assets.map(requestForStaticAsset);
  const uniqueUrls = new Set(requests.map(({ url }) => url));
  if (uniqueUrls.size !== requests.length) {
    throw new Error("PWA 静态缓存清单包含重复 URL");
  }

  const cache = await caches.open(CACHE_NAME);
  await cache.addAll(requests);
}

async function activateCurrentBuild(): Promise<void> {
  const cacheNames = await caches.keys();
  await Promise.all(
    cacheNames
      .filter((cacheName) => cacheName.startsWith(CACHE_PREFIX) && cacheName !== CACHE_NAME)
      .map((cacheName) => caches.delete(cacheName)),
  );
  await worker.clients.claim();
}

async function respondCacheFirst(request: Request): Promise<Response> {
  const cached = await caches.match(request, { cacheName: CACHE_NAME });
  if (cached) return cached;

  try {
    return await fetch(request);
  } catch (error) {
    if (request.mode === "navigate") {
      const [indexFallback, rootFallback] = await Promise.all([
        caches.match(new URL("index.html", worker.registration.scope), { cacheName: CACHE_NAME }),
        caches.match(new URL("./", worker.registration.scope), { cacheName: CACHE_NAME }),
      ]);
      const fallback = indexFallback ?? rootFallback;
      if (fallback) return fallback;
    }
    throw error;
  }
}

worker.addEventListener("install", (event: ExtendableEvent) => {
  event.waitUntil(installStaticAssets());
});

worker.addEventListener("message", (event: ExtendableMessageEvent) => {
  const messageType =
    typeof event.data === "string"
      ? event.data
      : event.data && typeof event.data === "object"
        ? (event.data as { type?: unknown }).type
        : undefined;
  if (messageType === "SKIP_WAITING") {
    event.waitUntil(worker.skipWaiting());
  }
});

worker.addEventListener("activate", (event: ExtendableEvent) => {
  event.waitUntil(activateCurrentBuild());
});

worker.addEventListener("fetch", (event: FetchEvent) => {
  const request = event.request;
  const url = new URL(request.url);
  if (
    request.method !== "GET" ||
    url.origin !== worker.location.origin ||
    !url.href.startsWith(worker.registration.scope) ||
    isApiUrl(url)
  ) {
    return;
  }

  event.respondWith(respondCacheFirst(request));
});

export {};
