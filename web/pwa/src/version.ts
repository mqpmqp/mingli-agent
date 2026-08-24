export type VersionBinding = {
  appBuildId: string;
  gitSha: string;
  wheelSha256: string;
  pyodideVersion: string;
  tzdataVersion: string;
};

export type VersionBindingField = keyof VersionBinding;

const VERSION_FIELDS: readonly VersionBindingField[] = [
  "appBuildId",
  "gitSha",
  "wheelSha256",
  "pyodideVersion",
  "tzdataVersion",
];

export class UpdateRequiredError extends Error {
  readonly code = "UPDATE_REQUIRED";
  readonly mismatches: VersionBindingField[];

  constructor(mismatches: VersionBindingField[]) {
    super("应用与离线运行资源版本不一致，请刷新并更新到最新版本后重试。");
    this.name = "UpdateRequiredError";
    this.mismatches = mismatches;
  }
}

export function assertVersionBinding(expected: VersionBinding, actual: VersionBinding): void {
  const mismatches = VERSION_FIELDS.filter((field) => expected[field] !== actual[field]);
  if (mismatches.length > 0) throw new UpdateRequiredError(mismatches);
}
