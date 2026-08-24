type RuntimeManifest = {
  app_build_id: string;
  git_sha: string;
  wheel: { filename: string; sha256: string };
  pyodide: { version: string; python_version: string; module: string; index: string };
  tzdata: { version: string; filename: string; sha256: string };
};

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
};

const metaBase = document.querySelector<HTMLMetaElement>('meta[name="mingli-runtime-base"]')?.content;
const runtimeBase = new URL(metaBase ?? "./runtime/", document.baseURI);
let pyodide: Pyodide;
let manifest: RuntimeManifest;
let versionInfo: RuntimeVersions;

async function fetchRequired(url: URL): Promise<Response> {
  const response = await fetch(url, { cache: "force-cache" });
  if (!response.ok) throw new Error(`无法加载离线运行资源：${url.pathname} (${response.status})`);
  return response;
}

async function installPureWheel(filename: string): Promise<void> {
  const url = new URL(filename, runtimeBase);
  const bytes = new Uint8Array(await (await fetchRequired(url)).arrayBuffer());
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

async function initialize(): Promise<void> {
  manifest = (await (await fetchRequired(new URL("runtime-manifest.json", runtimeBase))).json()) as RuntimeManifest;
  const pyodideModuleUrl = new URL(manifest.pyodide.module, runtimeBase).href;
  const pyodideModule = (await import(/* @vite-ignore */ pyodideModuleUrl)) as {
    loadPyodide(options: { indexURL: string }): Promise<Pyodide>;
  };
  pyodide = await pyodideModule.loadPyodide({ indexURL: new URL(manifest.pyodide.index, runtimeBase).href });
  await installPureWheel(manifest.tzdata.filename);
  await installPureWheel(manifest.wheel.filename);
  pyodide.runPython(`
import json
import sys
import tzdata
from zoneinfo import ZoneInfo
from mingli.bazi import DeterministicBaziEngine

_mingli_engine = DeterministicBaziEngine()
ZoneInfo("Asia/Shanghai")

def _mingli_calculate_json(payload_json):
    result = _mingli_engine.calculate(json.loads(payload_json))
    return json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _mingli_versions_json():
    return json.dumps({
        "python": ".".join(map(str, sys.version_info[:3])),
        "tzdata": tzdata.__version__,
    }, sort_keys=True)
`);
  const pythonVersions = JSON.parse(String(pyodide.runPython("_mingli_versions_json()"))) as {
    python: string;
    tzdata: string;
  };
  if (pythonVersions.tzdata !== manifest.tzdata.version) {
    throw new Error(`tzdata 版本不一致：${pythonVersions.tzdata} != ${manifest.tzdata.version}`);
  }
  if (!pythonVersions.python.startsWith("3.11.")) {
    throw new Error(`Pyodide Python 版本不受支持：${pythonVersions.python}`);
  }
  versionInfo = {
    buildId: manifest.app_build_id,
    gitSha: manifest.git_sha,
    pyodide: manifest.pyodide.version,
    python: pythonVersions.python,
    tzdata: pythonVersions.tzdata,
    wheelSha256: manifest.wheel.sha256,
  };
}

const ready = initialize();

async function calculate(input: Record<string, unknown>): Promise<Record<string, unknown>> {
  await ready;
  pyodide.globals.set("_mingli_payload_json", JSON.stringify(input));
  try {
    return JSON.parse(String(pyodide.runPython("_mingli_calculate_json(_mingli_payload_json)"))) as Record<
      string,
      unknown
    >;
  } finally {
    pyodide.globals.delete("_mingli_payload_json");
  }
}

async function versions(): Promise<Record<string, string>> {
  await ready;
  return { ...versionInfo };
}

window.__mingliPwa = { ready, calculate, versions };

export { calculate, ready, versions };
