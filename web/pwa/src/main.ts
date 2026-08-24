import "./styles.css";

import {
  isLeapMonthVisible,
  validateChartForm,
  type ChartFormValues,
} from "./form";
import {
  buildChatGptPrompt,
  buildCompactChartText,
  buildFullJson,
  formatLuckStartAge,
  mapChartCalculationError,
  type ChartPresentationData,
  type ChartResult,
} from "./presentation";
import { assertVersionBinding, type VersionBinding } from "./version";

declare const __MINGLI_BUILD_INFO__: VersionBinding;

type RuntimeSuccess = {
  ok: true;
  result: ChartResult;
  canonical_hash: string;
};

type RuntimeFailure = {
  ok: false;
  error: { code: string; message?: string };
};

type RuntimeOutcome = RuntimeSuccess | RuntimeFailure;

type RuntimeVersions = {
  buildId: string;
  gitSha: string;
  wheelSha256: string;
  pyodide: string;
  python: string;
  tzdata: string;
  zoneInfoAsiaShanghai: string;
};

type RuntimeModule = {
  ready: Promise<void>;
  calculateOutcome(input: Record<string, unknown>): Promise<RuntimeOutcome>;
  versions(): Promise<RuntimeVersions>;
};

function requiredElement<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector);
  if (!element) throw new Error(`页面缺少必要元素：${selector}`);
  return element;
}

const form = requiredElement<HTMLFormElement>("#chart-form");
const runtimeStatus = requiredElement<HTMLElement>('[data-testid="runtime-status"]');
const offlineReady = requiredElement<HTMLElement>('[data-testid="offline-ready"]');
const retryRuntime = requiredElement<HTMLButtonElement>('[data-testid="retry-runtime"]');
const calculateButton = requiredElement<HTMLButtonElement>('[data-testid="calculate"]');
const formError = requiredElement<HTMLElement>('[data-testid="form-error"]');
const calculationError = requiredElement<HTMLElement>('[data-testid="calculation-error"]');
const resultSection = requiredElement<HTMLElement>('[data-testid="result-section"]');
const resultJson = requiredElement<HTMLTextAreaElement>('[data-testid="result-json"]');
const trueSolarOutput = requiredElement<HTMLElement>("#output-true-solar-time");
const leapMonthRow = requiredElement<HTMLElement>('[data-testid="leap-month-row"]');
const leapMonthInput = requiredElement<HTMLInputElement>('[name="is_leap_month"]');
const actionFeedback = requiredElement<HTMLElement>('[data-testid="action-feedback"]');
const coordinateConfirmation = requiredElement<HTMLInputElement>('[name="coordinate_confirm"]');
const updateBanner = requiredElement<HTMLElement>('[data-testid="update-banner"]');

const expectedVersions: VersionBinding = __MINGLI_BUILD_INFO__;

let runtime: RuntimeModule | null = null;
let runtimeVersions: RuntimeVersions | null = null;
let currentPresentation: ChartPresentationData | null = null;
let feedbackRevision = 0;
let calculationRevision = 0;

function setRuntimeState(state: "loading" | "ready" | "error", message: string): void {
  runtimeStatus.dataset.state = state;
  runtimeStatus.textContent = message;
}

function setOfflineState(state: "preparing" | "ready" | "error", message: string): void {
  offlineReady.dataset.state = state;
  offlineReady.textContent = message;
}

function showUpdateBanner(): void {
  updateBanner.hidden = false;
}

function updateLeapMonthVisibility(): void {
  const calendar = new FormData(form).get("calendar")?.toString() ?? "";
  const visible = isLeapMonthVisible(calendar);
  leapMonthRow.hidden = !visible;
  leapMonthInput.disabled = !visible;
  if (!visible) leapMonthInput.checked = false;
}

function readFormValues(): ChartFormValues {
  const data = new FormData(form);
  return {
    gender: data.get("gender")?.toString() ?? "",
    calendar: data.get("calendar")?.toString() ?? "",
    birthDate: data.get("birth_date")?.toString() ?? "",
    birthTime: data.get("birth_time")?.toString() ?? "",
    timezone: data.get("timezone")?.toString() ?? "",
    birthLocationNote: data.get("birth_location_note")?.toString() ?? "",
    longitude: data.get("longitude")?.toString() ?? "",
    latitude: data.get("latitude")?.toString() ?? "",
    trueSolarTime: requiredElement<HTMLInputElement>('[name="true_solar_time"]').checked,
    isLeapMonth: !leapMonthInput.disabled && leapMonthInput.checked,
    fold: data.get("fold")?.toString() ?? "",
    coordinateConfirmed: requiredElement<HTMLInputElement>('[name="coordinate_confirm"]').checked,
  };
}

function hideMessages(): void {
  formError.hidden = true;
  formError.textContent = "";
  calculationError.hidden = true;
  calculationError.textContent = "";
}

function clearRenderedResult(): void {
  calculationRevision += 1;
  feedbackRevision += 1;
  currentPresentation = null;
  resultSection.hidden = true;
  resultSection.querySelectorAll<HTMLElement>("dd, .pillar-grid strong").forEach((element) => {
    element.textContent = "";
  });
  trueSolarOutput.removeAttribute("data-testid");
  resultJson.value = "";
  actionFeedback.textContent = "";
}

function showFormErrors(errors: Partial<Record<keyof ChartFormValues, string>>): void {
  const messages = [...new Set(Object.values(errors).filter((message): message is string => Boolean(message)))];
  formError.textContent = messages.join(" ");
  formError.hidden = false;
}

function showCalculationError(message: string): void {
  clearRenderedResult();
  calculationError.textContent = message;
  calculationError.hidden = false;
}

function setOutput(testId: string, value: string | number): void {
  const element = resultSection.querySelector<HTMLElement>(`[data-testid="${testId}"]`);
  if (!element) throw new Error(`结果页面缺少字段：${testId}`);
  element.textContent = String(value);
}

function requireResult(result: ChartResult): void {
  const strings = [
    result.method_id,
    result.calculation_version,
    result.calendar?.input_datetime,
    result.calendar?.corrected_datetime,
    result.pillars?.year,
    result.pillars?.month,
    result.pillars?.day,
    result.pillars?.hour,
    result.boundaries?.active_month_term,
    result.luck?.direction,
    result.luck?.adjacent_jie,
    result.luck?.adjacent_jie_utc,
    result.prediction_validity,
  ];
  if (strings.some((value) => typeof value !== "string" || value.length === 0)) {
    throw new Error("排盘引擎返回结果不完整，请重新加载运行环境后再试。");
  }
  if (!Number.isFinite(result.calendar.true_solar_correction_minutes)) {
    throw new Error("排盘结果缺少真太阳时修正数据。");
  }
  if (!Number.isFinite(result.calendar.equation_of_time_minutes)) {
    throw new Error("排盘结果缺少均时差数据。");
  }
  if (!Number.isFinite(result.luck.start_age_years)) {
    throw new Error("排盘结果缺少起运年龄数据。");
  }
  if (!Array.isArray(result.warnings)) throw new Error("排盘结果缺少 warnings 数据。");
}

function renderResult(outcome: RuntimeSuccess, versions: RuntimeVersions): void {
  const { result } = outcome;
  requireResult(result);
  if (
    result.prediction_validity === "REVIEW_REQUIRED" ||
    result.warnings.some((warning) => warning.includes("SOLAR_TERM_UNCERTAIN"))
  ) {
    throw new Error(mapChartCalculationError("SOLAR_TERM_UNCERTAIN"));
  }
  if (!/^sha256:[0-9a-f]{64}$/i.test(outcome.canonical_hash)) {
    throw new Error("排盘结果缺少有效的 canonical result hash。");
  }

  const presentation: ChartPresentationData = {
    result,
    canonicalHash: outcome.canonical_hash,
    gitSha: versions.gitSha,
    wheelSha256: versions.wheelSha256,
  };
  currentPresentation = presentation;

  setOutput("civil-birth-time", result.calendar.input_datetime);
  trueSolarOutput.setAttribute("data-testid", "result-true-solar-time");
  trueSolarOutput.textContent = result.calendar.true_solar_time_applied
    ? result.calendar.corrected_datetime
    : "未启用";
  setOutput("true-solar-correction-minutes", `${result.calendar.true_solar_correction_minutes} 分钟`);
  setOutput("equation-of-time-minutes", `${result.calendar.equation_of_time_minutes} 分钟`);
  setOutput("year-pillar", result.pillars.year);
  setOutput("month-pillar", result.pillars.month);
  setOutput("day-pillar", result.pillars.day);
  setOutput("hour-pillar", result.pillars.hour);
  setOutput("day-master", Array.from(result.pillars.day)[0] ?? "");
  setOutput("luck-direction", result.luck.direction === "forward" ? "顺行（forward）" : "逆行（reverse）");
  setOutput("luck-start-age-raw", `${result.luck.start_age_years} 岁`);
  setOutput("luck-start-age-readable", formatLuckStartAge(result.luck.start_age_years));
  setOutput("adjacent-solar-term", result.luck.adjacent_jie);
  setOutput("adjacent-solar-term-time", result.luck.adjacent_jie_utc);
  setOutput("current-month-term", result.boundaries.active_month_term);
  setOutput("method-id", result.method_id);
  setOutput("calculation-version", result.calculation_version);
  setOutput("git-sha", versions.gitSha);
  setOutput("wheel-sha256", versions.wheelSha256);
  setOutput("canonical-result-hash", outcome.canonical_hash);
  setOutput("prediction-validity", result.prediction_validity);
  setOutput("warnings", result.warnings.length > 0 ? result.warnings.join("；") : "无");
  resultJson.value = buildFullJson(presentation);
  resultSection.hidden = false;
}

async function copyText(text: string, successMessage: string): Promise<void> {
  const revision = ++feedbackRevision;
  try {
    await navigator.clipboard.writeText(text);
    if (revision !== feedbackRevision) return;
    actionFeedback.textContent = successMessage;
  } catch {
    if (revision !== feedbackRevision) return;
    actionFeedback.textContent = "复制失败，请确认浏览器已允许剪贴板权限。";
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error && error.message ? error.message : "未知错误";
}

async function loadRuntime(): Promise<void> {
  runtime = null;
  runtimeVersions = null;
  retryRuntime.hidden = true;
  calculateButton.disabled = true;
  setRuntimeState("loading", "正在初始化本地 Python 运行环境…");
  try {
    const loaded = (await import("./runtime")) as unknown as RuntimeModule;
    await loaded.ready;
    const versions = await loaded.versions();
    assertVersionBinding(expectedVersions, {
      appBuildId: versions.buildId,
      gitSha: versions.gitSha,
      wheelSha256: versions.wheelSha256,
      pyodideVersion: versions.pyodide,
      tzdataVersion: versions.tzdata,
    });
    if (versions.zoneInfoAsiaShanghai !== "verified") {
      throw new Error("Asia/Shanghai 时区数据验证失败，请重新加载运行环境。");
    }
    runtime = loaded;
    runtimeVersions = versions;
    calculateButton.disabled = false;
    setRuntimeState("ready", `本地排盘引擎已就绪（Python ${versions.python}），可以排盘。`);
  } catch (error) {
    const code = error && typeof error === "object" && "code" in error ? String(error.code) : "";
    if (code === "UPDATE_REQUIRED") showUpdateBanner();
    setRuntimeState("error", `运行环境初始化失败：${errorMessage(error)}`);
    retryRuntime.hidden = false;
  }
}

function networkLabel(): string {
  return navigator.onLine ? "当前在线" : "当前离线";
}

function refreshOfflineLabel(): void {
  if (offlineReady.dataset.state === "ready") {
    offlineReady.textContent = `离线资源已就绪 · ${networkLabel()}`;
  }
}

function observeServiceWorkerUpdate(registration: ServiceWorkerRegistration): void {
  const watchInstalling = (): void => {
    const installing = registration.installing;
    if (!installing) return;
    installing.addEventListener("statechange", () => {
      if (installing.state === "installed" && navigator.serviceWorker.controller) showUpdateBanner();
    });
  };
  registration.addEventListener("updatefound", watchInstalling);
  if (registration.waiting && navigator.serviceWorker.controller) showUpdateBanner();
}

async function waitForServiceWorkerControl(timeoutMs = 15_000): Promise<void> {
  if (navigator.serviceWorker.controller) return;

  await new Promise<void>((resolve, reject) => {
    let timeoutId: number;
    const cleanup = (): void => {
      window.clearTimeout(timeoutId);
      navigator.serviceWorker.removeEventListener("controllerchange", onControllerChange);
    };
    const onControllerChange = (): void => {
      if (!navigator.serviceWorker.controller) return;
      cleanup();
      resolve();
    };
    timeoutId = window.setTimeout(() => {
      cleanup();
      reject(new Error("Service Worker 尚未控制当前页面，请刷新后再离线使用。"));
    }, timeoutMs);
    navigator.serviceWorker.addEventListener("controllerchange", onControllerChange);
    onControllerChange();
  });
}

async function initializeServiceWorker(): Promise<void> {
  if (!("serviceWorker" in navigator)) {
    setOfflineState("error", "此浏览器不支持离线安装，请使用最新版移动浏览器。 ");
    return;
  }
  try {
    const scriptUrl = new URL("sw.js", document.baseURI);
    const registration = await navigator.serviceWorker.register(scriptUrl.href);
    observeServiceWorkerUpdate(registration);
    await navigator.serviceWorker.ready;
    await waitForServiceWorkerControl();
    setOfflineState("ready", `离线资源已就绪 · ${networkLabel()}`);
  } catch (error) {
    setOfflineState("error", `离线资源准备失败：${errorMessage(error)}`);
  }
}

async function activateAvailableUpdate(): Promise<void> {
  if (!("serviceWorker" in navigator)) {
    location.reload();
    return;
  }
  try {
    const registration = await navigator.serviceWorker.getRegistration();
    const waiting = registration?.waiting;
    if (!waiting) {
      location.reload();
      return;
    }
    navigator.serviceWorker.addEventListener(
      "controllerchange",
      () => location.reload(),
      { once: true },
    );
    waiting.postMessage({ type: "SKIP_WAITING" });
  } catch {
    location.reload();
  }
}

form.addEventListener("input", (event) => {
  const target = event.target;
  if (target instanceof HTMLInputElement && (target.name === "longitude" || target.name === "latitude")) {
    coordinateConfirmation.checked = false;
  }
  clearRenderedResult();
});

form.addEventListener("change", (event) => {
  const target = event.target;
  if (target instanceof HTMLInputElement && target.name === "calendar") updateLeapMonthVisibility();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideMessages();
  clearRenderedResult();

  const validation = validateChartForm(readFormValues());
  if (!validation.valid) {
    showFormErrors(validation.errors);
    return;
  }
  if (!runtime || !runtimeVersions) {
    showCalculationError("本地排盘引擎尚未就绪，请等待加载完成或重新加载运行环境。");
    return;
  }

  calculateButton.disabled = true;
  const revision = calculationRevision;
  const originalLabel = calculateButton.textContent;
  calculateButton.textContent = "正在排盘…";
  try {
    const outcome = await runtime.calculateOutcome(validation.input as unknown as Record<string, unknown>);
    if (revision !== calculationRevision) return;
    if (!outcome.ok) {
      showCalculationError(mapChartCalculationError(outcome.error.code));
      return;
    }
    renderResult(outcome, runtimeVersions);
  } catch (error) {
    if (revision !== calculationRevision) return;
    showCalculationError(`排盘计算未完成：${errorMessage(error)}`);
  } finally {
    calculateButton.disabled = false;
    calculateButton.textContent = originalLabel;
  }
});

requiredElement<HTMLButtonElement>('[data-testid="copy-summary"]').addEventListener("click", () => {
  if (currentPresentation) void copyText(buildCompactChartText(currentPresentation), "简版排盘已复制。 ");
});

requiredElement<HTMLButtonElement>('[data-testid="copy-json"]').addEventListener("click", () => {
  if (currentPresentation) void copyText(buildFullJson(currentPresentation), "完整 JSON 已复制。 ");
});

requiredElement<HTMLButtonElement>('[data-testid="copy-prompt"]').addEventListener("click", () => {
  if (currentPresentation) void copyText(buildChatGptPrompt(currentPresentation), "ChatGPT 解读提示词已复制。 ");
});

requiredElement<HTMLButtonElement>('[data-testid="download-json"]').addEventListener("click", () => {
  if (!currentPresentation) return;
  const url = URL.createObjectURL(new Blob([buildFullJson(currentPresentation)], { type: "application/json;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "mingli-bazi-result.json";
  link.click();
  URL.revokeObjectURL(url);
  feedbackRevision += 1;
  actionFeedback.textContent = "JSON 文件已下载。 ";
});

requiredElement<HTMLButtonElement>('[data-testid="clear-data"]').addEventListener("click", () => {
  form.reset();
  updateLeapMonthVisibility();
  hideMessages();
  clearRenderedResult();
});

retryRuntime.addEventListener("click", () => location.reload());
requiredElement<HTMLButtonElement>('[data-action="reload-app"]').addEventListener(
  "click",
  () => void activateAvailableUpdate(),
);
window.addEventListener("online", refreshOfflineLabel);
window.addEventListener("offline", refreshOfflineLabel);

updateLeapMonthVisibility();
void initializeServiceWorker();
void loadRuntime();
