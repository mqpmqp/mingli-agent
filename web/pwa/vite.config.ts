import { createHash } from "node:crypto";
import { existsSync, readFileSync, statSync } from "node:fs";
import { dirname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

type VersionBinding = {
  appBuildId: string;
  gitSha: string;
  wheelSha256: string;
  pyodideVersion: string;
  tzdataVersion: string;
};

type RuntimeFile = {
  path: string;
  bytes: number;
  sha256: string;
};

type RuntimeManifest = {
  app_build_id: string;
  first_load_bytes: number;
  git_sha: string;
  files: RuntimeFile[];
  pyodide: { version: string };
  tzdata: { version: string };
  wheel: { sha256: string };
};

type WebManifest = {
  icons?: Array<{ src?: unknown }>;
};

const PWA_ROOT = dirname(fileURLToPath(import.meta.url));
const PUBLIC_ROOT = resolve(PWA_ROOT, "public");
const RUNTIME_ROOT = resolve(PUBLIC_ROOT, "runtime");
const RUNTIME_MANIFEST_PATH = resolve(RUNTIME_ROOT, "runtime-manifest.json");
const WEB_MANIFEST_PATH = resolve(PUBLIC_ROOT, "manifest.webmanifest");
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;

function requireString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error("runtime manifest 字段 " + field + " 必须是非空字符串");
  }
  return value;
}

function requireSha256(value: unknown, field: string): string {
  const digest = requireString(value, field);
  if (!SHA256_PATTERN.test(digest)) {
    throw new Error("runtime manifest 字段 " + field + " 必须是小写 SHA256");
  }
  return digest;
}

function normalizeScopeRelativePath(value: unknown, field: string): string {
  const source = requireString(value, field).trim();
  if (source === "." || source === "./") return "./";
  if (
    source.startsWith("/") ||
    source.startsWith("\\") ||
    source.includes("\\") ||
    source.includes("?") ||
    source.includes("#")
  ) {
    throw new Error(field + " 必须是不含查询串的 scope-relative 路径: " + source);
  }

  const normalized = source.startsWith("./") ? source.slice(2) : source;
  const parts = normalized.split("/");
  if (parts.some((part) => part === "" || part === "." || part === "..")) {
    throw new Error(field + " 包含不安全的路径段: " + source);
  }
  return parts.join("/");
}

function parseRuntimeManifest(): RuntimeManifest {
  if (!existsSync(RUNTIME_MANIFEST_PATH)) {
    throw new Error("缺少 public/runtime/runtime-manifest.json；请先运行 runtime 构建脚本");
  }

  const raw = JSON.parse(readFileSync(RUNTIME_MANIFEST_PATH, "utf8")) as Record<string, unknown>;
  const pyodide = raw.pyodide as Record<string, unknown> | undefined;
  const tzdata = raw.tzdata as Record<string, unknown> | undefined;
  const wheel = raw.wheel as Record<string, unknown> | undefined;
  const rawFiles = raw.files;

  if (!pyodide || !tzdata || !wheel || !Array.isArray(rawFiles) || rawFiles.length === 0) {
    throw new Error("runtime manifest 缺少 pyodide、tzdata、wheel 或非空 files 清单");
  }

  const files = rawFiles.map((value, index): RuntimeFile => {
    if (!value || typeof value !== "object") {
      throw new Error("runtime manifest files[" + index + "] 必须是对象");
    }
    const item = value as Record<string, unknown>;
    const path = normalizeScopeRelativePath(item.path, "files[" + index + "].path");
    if (path === "./" || path === "runtime-manifest.json") {
      throw new Error("runtime manifest files[" + index + "].path 不能引用 runtime 根或 manifest 本身");
    }
    if (!Number.isSafeInteger(item.bytes) || (item.bytes as number) < 0) {
      throw new Error("runtime manifest files[" + index + "].bytes 必须是非负安全整数");
    }
    return {
      path,
      bytes: item.bytes as number,
      sha256: requireSha256(item.sha256, "files[" + index + "].sha256"),
    };
  });

  const uniquePaths = new Set(files.map(({ path }) => path));
  if (uniquePaths.size !== files.length) {
    throw new Error("runtime manifest files.path 必须唯一");
  }

  if (!Number.isSafeInteger(raw.first_load_bytes) || (raw.first_load_bytes as number) < 0) {
    throw new Error("runtime manifest first_load_bytes 必须是非负安全整数");
  }
  const expectedBytes = files.reduce((total, file) => total + file.bytes, 0);
  if (raw.first_load_bytes !== expectedBytes) {
    throw new Error(
      "runtime manifest first_load_bytes 不一致: manifest=" +
        String(raw.first_load_bytes) +
        ", files=" +
        expectedBytes,
    );
  }

  for (const file of files) {
    const absolutePath = resolve(RUNTIME_ROOT, ...file.path.split("/"));
    const runtimePrefix = RUNTIME_ROOT + sep;
    if (!absolutePath.startsWith(runtimePrefix) || !existsSync(absolutePath)) {
      throw new Error("runtime manifest 文件不存在或越界: " + file.path);
    }
    if (statSync(absolutePath).size !== file.bytes) {
      throw new Error("runtime manifest 文件大小不一致: " + file.path);
    }
    const actualSha256 = createHash("sha256").update(readFileSync(absolutePath)).digest("hex");
    if (actualSha256 !== file.sha256) {
      throw new Error("runtime manifest 文件 SHA256 不一致: " + file.path);
    }
  }

  return {
    app_build_id: requireString(raw.app_build_id, "app_build_id"),
    first_load_bytes: raw.first_load_bytes as number,
    git_sha: requireString(raw.git_sha, "git_sha"),
    files,
    pyodide: { version: requireString(pyodide.version, "pyodide.version") },
    tzdata: { version: requireString(tzdata.version, "tzdata.version") },
    wheel: { sha256: requireSha256(wheel.sha256, "wheel.sha256") },
  };
}

function readIconPaths(): string[] {
  if (!existsSync(WEB_MANIFEST_PATH)) {
    throw new Error("缺少 public/manifest.webmanifest");
  }
  const manifest = JSON.parse(readFileSync(WEB_MANIFEST_PATH, "utf8")) as WebManifest;
  if (!Array.isArray(manifest.icons) || manifest.icons.length === 0) {
    throw new Error("manifest.webmanifest 必须声明至少一个图标");
  }

  return manifest.icons.map((icon, index) => {
    const path = normalizeScopeRelativePath(icon.src, "manifest.icons[" + index + "].src");
    if (path === "./") throw new Error("manifest.icons[" + index + "].src 不能指向应用根目录");
    const absolutePath = resolve(PUBLIC_ROOT, ...path.split("/"));
    const publicPrefix = PUBLIC_ROOT + sep;
    if (!absolutePath.startsWith(publicPrefix) || !existsSync(absolutePath)) {
      throw new Error("manifest 图标不存在或越界: " + path);
    }
    return path;
  });
}

function buildVersionBinding(manifest: RuntimeManifest): VersionBinding {
  return {
    appBuildId: manifest.app_build_id,
    gitSha: manifest.git_sha,
    wheelSha256: manifest.wheel.sha256,
    pyodideVersion: manifest.pyodide.version,
    tzdataVersion: manifest.tzdata.version,
  };
}

function pwaAssetsPlugin(
  appBinding: VersionBinding,
  runtimeFiles: RuntimeFile[],
  iconPaths: string[],
): Plugin {
  const versionMeta = [
    ["mingli-app-build-id", appBinding.appBuildId],
    ["mingli-git-sha", appBinding.gitSha],
    ["mingli-wheel-sha256", appBinding.wheelSha256],
    ["mingli-pyodide-version", appBinding.pyodideVersion],
    ["mingli-tzdata-version", appBinding.tzdataVersion],
  ] as const;

  return {
    name: "mingli-pwa-assets",
    apply: "build",
    enforce: "post",
    transformIndexHtml(html) {
      let transformed = html;
      for (const [name] of versionMeta) {
        const metaTag = new RegExp("<meta\\s+[^>]*name=([\"'])" + name + "\\1[^>]*>", "giu");
        transformed = transformed.replace(metaTag, "");
      }
      return {
        html: transformed,
        tags: versionMeta.map(([name, content]) => ({
          tag: "meta",
          attrs: { name, content },
          injectTo: "head" as const,
        })),
      };
    },
    generateBundle(_options, bundle) {
      const bundlePaths = Object.keys(bundle)
        .filter((fileName) => fileName !== "pwa-assets.json")
        .map((fileName) => normalizeScopeRelativePath(fileName, "bundle." + fileName))
        .sort();
      const runtimePaths = runtimeFiles.map(({ path }) => "runtime/" + path).sort();
      const assets = [
        "./",
        "index.html",
        "manifest.webmanifest",
        ...iconPaths.sort(),
        ...bundlePaths,
        "runtime/runtime-manifest.json",
        ...runtimePaths,
      ].filter((path, index, values) => values.indexOf(path) === index);

      this.emitFile({
        type: "asset",
        fileName: "pwa-assets.json",
        source:
          JSON.stringify(
            {
              schemaVersion: "mingli-pwa-assets@1.0",
              appBinding,
              assets,
            },
            null,
            2,
          ) + "\n",
      });
    },
  };
}

export default defineConfig(() => {
  const runtimeManifest = parseRuntimeManifest();
  const appBinding = buildVersionBinding(runtimeManifest);
  const iconPaths = readIconPaths();

  return {
    base: "./",
    define: {
      __MINGLI_BUILD_INFO__: JSON.stringify(appBinding),
    },
    plugins: [pwaAssetsPlugin(appBinding, runtimeManifest.files, iconPaths)],
    build: {
      target: "es2022",
      outDir: "dist",
      emptyOutDir: true,
      rollupOptions: {
        input: {
          index: resolve(PWA_ROOT, "index.html"),
          sw: resolve(PWA_ROOT, "src/sw.ts"),
        },
        output: {
          entryFileNames: ({ name }) => (name === "sw" ? "sw.js" : "assets/[name]-[hash].js"),
          chunkFileNames: "assets/[name]-[hash].js",
          assetFileNames: "assets/[name]-[hash][extname]",
        },
      },
    },
    test: {
      coverage: {
        provider: "v8",
        include: ["src/form.ts", "src/presentation.ts", "src/version.ts"],
        thresholds: {
          branches: 80,
          functions: 80,
          lines: 80,
          statements: 80,
        },
      },
    },
  };
});
