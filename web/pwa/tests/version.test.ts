import { describe, expect, it } from "vitest";

import { assertVersionBinding, type VersionBinding } from "../src/version";

const expected: VersionBinding = {
  appBuildId: "de2111fa81657da32632",
  gitSha: "4fc75751354300dd417c0d28e4f1879e797973b5",
  wheelSha256: "aed1ef4b21f8118eb2df6bb1d8d9e83a5073d4d4fbbb86cba1c5e8b01ca37958",
  pyodideVersion: "0.25.1",
  tzdataVersion: "2025.2",
};

describe("PWA 应用与 Python 运行时版本绑定", () => {
  it("五项版本标识完全一致时允许继续排盘", () => {
    expect(() => assertVersionBinding(expected, { ...expected })).not.toThrow();
  });

  it.each([
    ["appBuildId", "different-build"],
    ["gitSha", "different-git-sha"],
    ["wheelSha256", "different-wheel-sha"],
    ["pyodideVersion", "0.26.0"],
    ["tzdataVersion", "2026.1"],
  ] as const)("%s 不一致时以 UPDATE_REQUIRED 阻止静默混用", (field, value) => {
    const actual = { ...expected, [field]: value };

    try {
      assertVersionBinding(expected, actual);
      throw new Error("expected version mismatch to throw");
    } catch (error) {
      expect(error).toMatchObject({
        code: "UPDATE_REQUIRED",
        mismatches: expect.arrayContaining([field]),
      });
      expect((error as Error).message).toMatch(/刷新|更新/u);
    }
  });

  it("一次报告全部不一致项，避免修复一项后继续使用混合资源", () => {
    const actual: VersionBinding = {
      appBuildId: "old-build",
      gitSha: "old-git",
      wheelSha256: "old-wheel",
      pyodideVersion: "old-pyodide",
      tzdataVersion: "old-tzdata",
    };

    try {
      assertVersionBinding(expected, actual);
      throw new Error("expected version mismatch to throw");
    } catch (error) {
      expect(error).toMatchObject({
        code: "UPDATE_REQUIRED",
        mismatches: [
          "appBuildId",
          "gitSha",
          "wheelSha256",
          "pyodideVersion",
          "tzdataVersion",
        ],
      });
    }
  });
});
