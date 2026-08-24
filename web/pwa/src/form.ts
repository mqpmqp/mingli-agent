export type ChartFormValues = {
  gender: string;
  calendar: string;
  birthDate: string;
  birthTime: string;
  timezone: string;
  birthLocationNote: string;
  longitude: string;
  latitude: string;
  trueSolarTime: boolean;
  isLeapMonth: boolean;
  fold: string;
  coordinateConfirmed?: boolean;
};

export type ChartEngineInput = {
  gender: "male" | "female";
  calendar: "solar" | "lunar";
  birth_date: string;
  birth_time: string;
  timezone: string;
  longitude?: number;
  latitude?: number;
  true_solar_time: boolean;
  is_leap_month?: boolean;
  fold: 0 | 1;
};

export type ChartFormErrors = Partial<Record<keyof ChartFormValues, string>>;

export type ChartFormValidation =
  | { valid: true; errors: ChartFormErrors; input: ChartEngineInput }
  | { valid: false; errors: ChartFormErrors; input?: undefined };

export function isLeapMonthVisible(calendar: string): boolean {
  return calendar === "lunar";
}

function isValidDate(value: string, calendar: "solar" | "lunar"): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return false;
  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (year < 1901 || year > 2099 || month < 1 || month > 12 || day < 1) return false;
  if (calendar === "lunar") return day <= 30;
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

function isValidTimezone(value: string): boolean {
  try {
    new Intl.DateTimeFormat("zh-CN", { timeZone: value }).format();
    return true;
  } catch {
    return false;
  }
}

function parseCoordinate(
  value: string,
  minimum: number,
  maximum: number,
): { empty: true } | { empty: false; value: number } | { error: true } {
  const normalized = value.trim();
  if (!normalized) return { empty: true };
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed) || parsed < minimum || parsed > maximum) return { error: true };
  return { empty: false, value: parsed };
}

export function validateChartForm(values: ChartFormValues): ChartFormValidation {
  const errors: ChartFormErrors = {};
  const gender = values.gender.trim();
  const calendar = values.calendar.trim();
  const birthDate = values.birthDate.trim();
  const birthTime = values.birthTime.trim();
  const timezone = values.timezone.trim();

  if (gender !== "male" && gender !== "female") errors.gender = "请选择性别。";
  if (calendar !== "solar" && calendar !== "lunar") errors.calendar = "请选择阳历或农历。";

  if (!birthDate) {
    errors.birthDate = "请填写出生日期。";
  } else if (
    (calendar === "solar" || calendar === "lunar") &&
    !isValidDate(birthDate, calendar)
  ) {
    errors.birthDate = "出生日期无效，请填写 1901 至 2099 年内的有效日期。";
  }

  if (!birthTime) {
    errors.birthTime = "请填写出生时间。";
  } else if (!/^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$/.test(birthTime)) {
    errors.birthTime = "出生时间无效，请按 24 小时制重新填写。";
  }

  if (!timezone) {
    errors.timezone = "请填写 IANA 时区。";
  } else if (!isValidTimezone(timezone)) {
    errors.timezone = "时区无效，请填写有效的 IANA 时区名称。";
  }

  const longitude = parseCoordinate(values.longitude, -180, 180);
  const latitude = parseCoordinate(values.latitude, -90, 90);
  if ("error" in longitude) errors.longitude = "经度必须介于 -180 和 180 之间。";
  if ("error" in latitude) errors.latitude = "纬度必须介于 -90 和 90 之间。";
  if (values.trueSolarTime && "empty" in longitude && longitude.empty) {
    errors.longitude = "启用真太阳时必须填写经度，请确认后重新提交。";
  }

  const fold = values.fold.trim();
  if (fold !== "0" && fold !== "1") errors.fold = "重叠时间 fold 只允许填写 0 或 1。";
  if (values.coordinateConfirmed === false) {
    errors.coordinateConfirmed = "请确认经度、纬度坐标后再排盘。";
  }

  if (Object.keys(errors).length > 0) return { valid: false, errors };

  const input: ChartEngineInput = {
    gender: gender as ChartEngineInput["gender"],
    calendar: calendar as ChartEngineInput["calendar"],
    birth_date: birthDate,
    birth_time: birthTime,
    timezone,
    true_solar_time: values.trueSolarTime,
    fold: Number(fold) as 0 | 1,
  };
  if ("value" in longitude) input.longitude = longitude.value;
  if ("value" in latitude) input.latitude = latitude.value;
  if (calendar === "lunar") input.is_leap_month = values.isLeapMonth;
  return { valid: true, errors, input };
}
