import { assertVersionBinding, type VersionBinding } from "./version";

type JsonRecord = Record<string, unknown>;

type RuntimeFileRecord = {
  path: string;
  bytes: number;
  sha256: string;
};

type RuntimeManifest = {
  schema_version: string;
  app_build_id: string;
  git_sha: string;
  wheel: { filename: string; sha256: string };
  pyodide: {
    version: string;
    python_version: string;
    module: string;
    index: string;
    bootstrap: { asm_js: string; wasm: string; stdlib: string; lockfile: string };
  };
  tzdata: { version: string; filename: string; sha256: string };
  parity: { filename: string; case_count: number };
  files: RuntimeFileRecord[];
  first_load_bytes: number;
};

type SuccessfulOutcome = {
  ok: true;
  result: JsonRecord;
  canonical_hash: string;
};

type ErrorOutcome = {
  ok: false;
  error: { code: string };
};

type RuntimeOutcome = SuccessfulOutcome | ErrorOutcome;

type DeterminismSample = {
  canonical_hash: string;
  pillars: JsonRecord;
  luck: JsonRecord;
};

type DeterminismSummary = {
  runs: number;
  samples: DeterminismSample[];
};

declare const __MINGLI_BUILD_INFO__: VersionBinding;

type Pyodide = {
  FS: {
    writeFile(path: string, data: Uint8Array): void;
    unlink(path: string): void;
  };
  globals: {
    set(name: string, value: unknown): void;
    delete(name: string): void;
  };
  runPython(code: string): unknown;
};

type RuntimeVersions = {
  buildId: string;
  gitSha: string;
  pyodide: string;
  python: string;
  tzdata: string;
  wheelSha256: string;
  zoneInfoAsiaShanghai: "verified";
};

const metaBase = document.querySelector<HTMLMetaElement>('meta[name="mingli-runtime-base"]')?.content;
const runtimeBase = new URL(metaBase ?? "./runtime/", document.baseURI);
let pyodide: Pyodide;
let manifest: RuntimeManifest;
let versionInfo: RuntimeVersions;

const SHA256_PATTERN = /^[0-9a-f]{64}$/u;

function runtimeUrl(path: string, allowTrailingSlash = false): URL {
  const normalized = allowTrailingSlash && path.endsWith("/") ? path.slice(0, -1) : path;
  if (
    normalized.length === 0 ||
    normalized.startsWith("/") ||
    normalized.includes("\\") ||
    normalized.split("/").some((part) => part === "" || part === "." || part === "..")
  ) {
    throw new Error(`运行资源清单包含不安全路径：${path}`);
  }
  const url = new URL(path, runtimeBase);
  if (url.origin !== runtimeBase.origin || !url.href.startsWith(runtimeBase.href)) {
    throw new Error(`运行资源路径超出离线资源目录：${path}`);
  }
  return url;
}

function validateManifest(candidate: unknown): RuntimeManifest {
  if (candidate === null || typeof candidate !== "object" || Array.isArray(candidate)) {
    throw new Error("运行资源清单格式无效");
  }
  const value = candidate as RuntimeManifest;
  if (value.schema_version !== "mingli-pwa-runtime-manifest@1.0") {
    throw new Error("运行资源清单版本不受支持");
  }
  if (
    typeof value.app_build_id !== "string" ||
    typeof value.git_sha !== "string" ||
    !value.wheel ||
    typeof value.wheel.filename !== "string" ||
    !SHA256_PATTERN.test(value.wheel.sha256) ||
    !value.pyodide ||
    typeof value.pyodide.version !== "string" ||
    typeof value.pyodide.python_version !== "string" ||
    typeof value.pyodide.module !== "string" ||
    typeof value.pyodide.index !== "string" ||
    !value.pyodide.bootstrap ||
    typeof value.pyodide.bootstrap.asm_js !== "string" ||
    typeof value.pyodide.bootstrap.wasm !== "string" ||
    typeof value.pyodide.bootstrap.stdlib !== "string" ||
    typeof value.pyodide.bootstrap.lockfile !== "string" ||
    !value.tzdata ||
    typeof value.tzdata.version !== "string" ||
    typeof value.tzdata.filename !== "string" ||
    !SHA256_PATTERN.test(value.tzdata.sha256) ||
    !value.parity ||
    typeof value.parity.filename !== "string" ||
    !Number.isSafeInteger(value.parity.case_count) ||
    !Array.isArray(value.files) ||
    !Number.isSafeInteger(value.first_load_bytes) ||
    value.first_load_bytes < 0
  ) {
    throw new Error("运行资源清单字段无效");
  }

  runtimeUrl(value.wheel.filename);
  runtimeUrl(value.tzdata.filename);
  runtimeUrl(value.pyodide.module);
  runtimeUrl(value.pyodide.index, true);
  const pyodidePaths = [value.pyodide.module, ...Object.values(value.pyodide.bootstrap)];
  for (const path of pyodidePaths) {
    runtimeUrl(path);
    if (!path.startsWith(value.pyodide.index)) {
      throw new Error(`Pyodide bootstrap 路径不在 index 目录内：${path}`);
    }
  }
  runtimeUrl(value.parity.filename);

  const seen = new Set<string>();
  let previousPath = "";
  let totalBytes = 0;
  for (const record of value.files) {
    if (
      !record ||
      typeof record.path !== "string" ||
      !Number.isSafeInteger(record.bytes) ||
      record.bytes < 0 ||
      !SHA256_PATTERN.test(record.sha256)
    ) {
      throw new Error("运行资源文件清单字段无效");
    }
    runtimeUrl(record.path);
    if (seen.has(record.path) || (previousPath !== "" && record.path <= previousPath)) {
      throw new Error(`运行资源文件清单重复或未排序：${record.path}`);
    }
    seen.add(record.path);
    previousPath = record.path;
    totalBytes += record.bytes;
  }
  if (!Number.isSafeInteger(totalBytes) || totalBytes !== value.first_load_bytes) {
    throw new Error("运行资源文件总字节数与清单不一致");
  }
  for (const path of pyodidePaths) {
    if (!seen.has(path)) throw new Error(`Pyodide bootstrap 不在完整性清单中：${path}`);
  }
  for (const [path, digest] of [
    [value.wheel.filename, value.wheel.sha256],
    [value.tzdata.filename, value.tzdata.sha256],
  ] as const) {
    const record = value.files.find((item) => item.path === path);
    if (!record || record.sha256 !== digest) {
      throw new Error(`运行资源摘要与文件清单不一致：${path}`);
    }
  }
  return value;
}

async function fetchRequired(url: URL): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(url, { cache: "force-cache" });
  } catch {
    throw new Error(`无法加载离线运行资源：${url.pathname}`);
  }
  if (!response.ok) throw new Error(`无法加载离线运行资源：${url.pathname} (${response.status})`);
  return response;
}

async function verifiedBytes(filename: string, expectedSha256: string): Promise<Uint8Array<ArrayBuffer>> {
  const record = manifest.files.find((item) => item.path === filename);
  if (!record || record.sha256 !== expectedSha256) {
    throw new Error(`运行资源不在完整性清单中：${filename}`);
  }
  const buffer = await (await fetchRequired(runtimeUrl(filename))).arrayBuffer();
  if (buffer.byteLength !== record.bytes) {
    throw new Error(`运行资源字节数校验失败：${filename}`);
  }
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  const actualSha256 = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  if (actualSha256 !== expectedSha256) {
    throw new Error(`运行资源 SHA256 校验失败：${filename}`);
  }
  return new Uint8Array(buffer);
}

type PyodideLoaderModule = {
  loadPyodide(options: {
    indexURL: string;
    stdLibURL: string;
    lockFileURL: string;
  }): Promise<Pyodide>;
};

type PyodideBootstrapGlobal = typeof globalThis & {
  _createPyodideModule?: unknown;
};

function runtimeRecord(filename: string): RuntimeFileRecord {
  const record = manifest.files.find((item) => item.path === filename);
  if (!record) throw new Error("运行资源不在完整性清单中：" + filename);
  return record;
}

async function verifiedManifestBytes(filename: string): Promise<Uint8Array<ArrayBuffer>> {
  const record = runtimeRecord(filename);
  return verifiedBytes(record.path, record.sha256);
}

async function importJavaScriptBytes(bytes: Uint8Array<ArrayBuffer>): Promise<Record<string, unknown>> {
  const objectUrl = URL.createObjectURL(new Blob([bytes], { type: "text/javascript" }));
  try {
    return (await import(/* @vite-ignore */ objectUrl)) as Record<string, unknown>;
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

function requestHref(input: RequestInfo | URL): string {
  if (typeof input === "string") return new URL(input, document.baseURI).href;
  if (input instanceof URL) return input.href;
  return input.url;
}

async function loadVerifiedPyodide(): Promise<Pyodide> {
  const bootstrap = manifest.pyodide.bootstrap;
  const [moduleBytes, asmBytes, wasmBytes, stdlibBytes, lockfileBytes] = await Promise.all([
    verifiedManifestBytes(manifest.pyodide.module),
    verifiedManifestBytes(bootstrap.asm_js),
    verifiedManifestBytes(bootstrap.wasm),
    verifiedManifestBytes(bootstrap.stdlib),
    verifiedManifestBytes(bootstrap.lockfile),
  ]);

  const importedModule = await importJavaScriptBytes(moduleBytes);
  if (typeof importedModule.loadPyodide !== "function") {
    throw new Error("Pyodide 模块缺少 loadPyodide 导出");
  }
  const loader = importedModule as unknown as PyodideLoaderModule;

  const pyodideGlobal = globalThis as PyodideBootstrapGlobal;
  delete pyodideGlobal._createPyodideModule;
  await importJavaScriptBytes(asmBytes);
  if (typeof pyodideGlobal._createPyodideModule !== "function") {
    throw new Error("Pyodide bootstrap 未注册 _createPyodideModule");
  }

  const indexURL = new URL(manifest.pyodide.index, runtimeBase).href;
  const wasmURL = runtimeUrl(bootstrap.wasm).href;
  const stdLibURL = URL.createObjectURL(new Blob([stdlibBytes], { type: "application/zip" }));
  const lockFileURL = URL.createObjectURL(new Blob([lockfileBytes], { type: "application/json" }));
  const originalFetch = globalThis.fetch;
  const verifiedFetch: typeof fetch = async (input, init) => {
    if (requestHref(input) === wasmURL) {
      return new Response(wasmBytes.slice(), {
        status: 200,
        headers: { "Content-Type": "application/wasm" },
      });
    }
    return originalFetch(input, init);
  };

  globalThis.fetch = verifiedFetch;
  try {
    return await loader.loadPyodide({ indexURL, stdLibURL, lockFileURL });
  } finally {
    globalThis.fetch = originalFetch;
    URL.revokeObjectURL(stdLibURL);
    URL.revokeObjectURL(lockFileURL);
    delete pyodideGlobal._createPyodideModule;
  }
}

async function installPureWheel(filename: string, expectedSha256: string): Promise<void> {
  const bytes = await verifiedBytes(filename, expectedSha256);
  const safeName = filename.split("/").at(-1)?.replace(/[^a-zA-Z0-9_.-]/g, "_") ?? "package.whl";
  const virtualPath = `/tmp/${safeName}`;
  pyodide.FS.writeFile(virtualPath, bytes);
  pyodide.globals.set("_mingli_wheel_path", virtualPath);
  try {
    pyodide.runPython(`
import sysconfig
import zipfile
with zipfile.ZipFile(_mingli_wheel_path) as _wheel:
    _wheel.extractall(sysconfig.get_paths()["purelib"])
`);
  } finally {
    pyodide.globals.delete("_mingli_wheel_path");
    pyodide.FS.unlink(virtualPath);
  }
}

async function installNamedWheel(filename: string, expectedSha256: string, label: string): Promise<void> {
  try {
    await installPureWheel(filename, expectedSha256);
  } catch (error) {
    const reason = error instanceof Error && error.message ? error.message : String(error);
    throw new Error(`${label}加载失败：${reason}`);
  }
}

async function initialize(): Promise<void> {
  const manifestResponse = await fetchRequired(new URL("runtime-manifest.json", runtimeBase));
  manifest = validateManifest(await manifestResponse.json());
  const runtimeBinding: VersionBinding = {
    appBuildId: manifest.app_build_id,
    gitSha: manifest.git_sha,
    wheelSha256: manifest.wheel.sha256,
    pyodideVersion: manifest.pyodide.version,
    tzdataVersion: manifest.tzdata.version,
  };
  const expectedBinding =
    typeof __MINGLI_BUILD_INFO__ === "undefined" ? runtimeBinding : __MINGLI_BUILD_INFO__;
  assertVersionBinding(expectedBinding, runtimeBinding);
  pyodide = await loadVerifiedPyodide();
  await installNamedWheel(manifest.tzdata.filename, manifest.tzdata.sha256, "时区数据 wheel");
  await installNamedWheel(manifest.wheel.filename, manifest.wheel.sha256, "排盘引擎 wheel");
  pyodide.runPython(`
import hashlib
import json
import sys
import tzdata
from zoneinfo import ZoneInfo
from mingli.bazi import DeterministicBaziEngine
from mingli.errors import ChartCalculationError

_mingli_engine = DeterministicBaziEngine()
ZoneInfo("Asia/Shanghai")

def _mingli_canonical_hash(result):
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()

def _mingli_calculate_json(payload_json):
    result = _mingli_engine.calculate(json.loads(payload_json))
    return json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _mingli_calculate_outcome_json(payload_json):
    try:
        result = _mingli_engine.calculate(json.loads(payload_json))
    except ChartCalculationError as exc:
        outcome = {"ok": False, "error": {"code": exc.code}}
    else:
        outcome = {"ok": True, "result": result, "canonical_hash": _mingli_canonical_hash(result)}
    return json.dumps(outcome, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _mingli_determinism_json(payload_json, runs):
    samples = []
    for _ in range(runs):
        result = _mingli_engine.calculate(json.loads(payload_json))
        samples.append({
            "canonical_hash": _mingli_canonical_hash(result),
            "pillars": result["pillars"],
            "luck": result["luck"],
        })
    return json.dumps({"runs": runs, "samples": samples}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _mingli_versions_json():
    return json.dumps({
        "python": ".".join(map(str, sys.version_info[:3])),
        "tzdata": tzdata.__version__,
        "zoneInfoAsiaShanghai": "verified",
    }, sort_keys=True)
`);
  const pythonVersions = JSON.parse(String(pyodide.runPython("_mingli_versions_json()"))) as {
    python: string;
    tzdata: string;
    zoneInfoAsiaShanghai: string;
  };
  if (pythonVersions.tzdata !== manifest.tzdata.version) {
    throw new Error(`tzdata 版本不一致：${pythonVersions.tzdata} != ${manifest.tzdata.version}`);
  }
  if (pythonVersions.python !== manifest.pyodide.python_version) {
    throw new Error(`Pyodide Python 版本不一致：${pythonVersions.python} != ${manifest.pyodide.python_version}`);
  }
  if (pythonVersions.zoneInfoAsiaShanghai !== "verified") {
    throw new Error("Asia/Shanghai ZoneInfo 校验失败");
  }
  versionInfo = {
    buildId: manifest.app_build_id,
    gitSha: manifest.git_sha,
    pyodide: manifest.pyodide.version,
    python: pythonVersions.python,
    tzdata: pythonVersions.tzdata,
    zoneInfoAsiaShanghai: "verified",
    wheelSha256: manifest.wheel.sha256,
  };
}

type RuntimeApi = {
  ready: Promise<void>;
  calculate(input: JsonRecord): Promise<JsonRecord>;
  calculateOutcome(input: JsonRecord): Promise<RuntimeOutcome>;
  determinism(input: JsonRecord, runs: number): Promise<DeterminismSummary>;
  versions(): Promise<Record<string, string>>;
};

const ready = initialize();

async function calculate(input: JsonRecord): Promise<JsonRecord> {
  await ready;
  pyodide.globals.set("_mingli_payload_json", JSON.stringify(input));
  try {
    return JSON.parse(String(pyodide.runPython("_mingli_calculate_json(_mingli_payload_json)"))) as JsonRecord;
  } finally {
    pyodide.globals.delete("_mingli_payload_json");
  }
}

async function calculateOutcome(input: JsonRecord): Promise<RuntimeOutcome> {
  await ready;
  pyodide.globals.set("_mingli_payload_json", JSON.stringify(input));
  try {
    return JSON.parse(
      String(pyodide.runPython("_mingli_calculate_outcome_json(_mingli_payload_json)")),
    ) as RuntimeOutcome;
  } finally {
    pyodide.globals.delete("_mingli_payload_json");
  }
}

async function determinism(input: JsonRecord, runs: number): Promise<DeterminismSummary> {
  if (!Number.isSafeInteger(runs) || runs < 1 || runs > 100) {
    throw new RangeError("determinism runs 必须是 1 到 100 的整数");
  }
  await ready;
  pyodide.globals.set("_mingli_payload_json", JSON.stringify(input));
  pyodide.globals.set("_mingli_runs", runs);
  try {
    return JSON.parse(
      String(pyodide.runPython("_mingli_determinism_json(_mingli_payload_json, _mingli_runs)")),
    ) as DeterminismSummary;
  } finally {
    pyodide.globals.delete("_mingli_payload_json");
    pyodide.globals.delete("_mingli_runs");
  }
}

async function versions(): Promise<Record<string, string>> {
  await ready;
  return { ...versionInfo };
}

const runtimeApi = { ready, calculate, calculateOutcome, determinism, versions } satisfies RuntimeApi;
const runtimeWindow = window as typeof window & { __mingliPwa?: RuntimeApi };
runtimeWindow.__mingliPwa = runtimeApi;

export { calculate, calculateOutcome, determinism, ready, versions };
